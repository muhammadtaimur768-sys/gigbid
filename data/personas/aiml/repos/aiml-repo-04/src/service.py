from qdrant_client import QdrantClient

client = QdrantClient(url=QDRANT_URL)
hits = client.search(collection_name='docs', query_vector=vec, limit=8)


from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

chain = prompt | llm | StrOutputParser()
