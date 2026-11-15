from qdrant_client import QdrantClient

client = QdrantClient(url=QDRANT_URL)
hits = client.search(collection_name='docs', query_vector=vec, limit=8)


SYSTEM = open('prompts/extract.md').read()
messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': doc}]


from sklearn.metrics import classification_report

print(classification_report(y_true, y_pred, digits=3))
