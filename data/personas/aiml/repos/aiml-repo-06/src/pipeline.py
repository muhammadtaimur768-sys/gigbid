SYSTEM = open('prompts/extract.md').read()
messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': doc}]


from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

chain = prompt | llm | StrOutputParser()
