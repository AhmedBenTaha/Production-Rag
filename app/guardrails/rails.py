import logfire 
from langchain_groq import ChatGroq 
from nemoguardrails import RailsConfig, LLMRails 
from app.config import settings 
from app.guardrails.colang_rules import (
                                COLANG_CONTENT, YAML_CONTENT, RAIL_INDICATORS, )


_rails:LLMRails|None=None

def initialize_rails() -> None:
    """ Build the NeMo LLMRails singleton at app startup. 
    Uses llama-3.1-8b-instant as a fast guardrail model for: 
    - Off-topic detection 
    - Jailbreak detection 
    - Greeting / farewell / capability handling The heavier model remains reserved for the Agentic RAG pipeline. 
    """
    
    global _rails
    if _rails is not None:
        logfire.info("🛡️ NeMo Guardrails already initialised.")
        return
    
    guard_llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.1-8b-instant",
        temperature=0,
    )
    
    config = RailsConfig.from_content(
        colang_content=COLANG_CONTENT,
        yaml_content=YAML_CONTENT
    )
    _rail = LLMRails(
        config=config,
        llm=guard_llm
    )
    logfire.info( "🛡️ NeMo Guardrails initialised "
                 "(llama-3.1-8b-instant)." )
    
    def guard(message: str) -> tuple[bool, str | None]:
        """ Run a user message through the NeMo Guardrails gate.
        Returns: 
        (True, rail_response) 
        A guardrail fired. 
        The application should return the rail response immediately and skip the Agentic RAG pipeline. 
        (False, None)
        The message passed the guardrails and can continue to the LangGraph Agentic RAG pipeline.
        """
        
        # Guardrails availability check
        if _rails is None:
            logfire.warning("⚠️ Guardrails not initialised — skipping gate.")
            return False,None
        
        # Basic input validation
        
        if not message or not message.strip():
            logfire.warning( "⚠️ Empty user message received." )
            return False,None
        
        message = message.strip()
        
        # Run NeMo Guardrails
        with logfire.span("🛡️ Guardrails Check"):
            try:
                result = _rails.generate(messages={
                    "role":"user",
                    "content":message
                })
                
                # Extract assistant response
                if isinstance(result, dict):
                    content = result.get("content","")
                else: 
                    content = str(result)
                content = content.strip() 
                
                # Detect fired rail
                fired_indicator = next( 
                                       ( 
                                        indicator 
                                        for indicator in RAIL_INDICATORS 
                                        if indicator.lower() in content.lower()
                                        ),
                                       None, 
                                       )   
                if fired_indicator:
                    logfire.info("🛡️ Guardrail fired", query=message[:80], indicator=fired_indicator,)
                    return True,content
                
                # Guardrails passed
                logfire.info( "✅ Guardrails passed.", query=message[:80], ) 
                return False, None
            except Exception as e: 
                logfire.error( "❌ Guardrails check failed.", error=str(e), )
                
                return False, None