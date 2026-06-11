from qdrant_client import QdrantClient, models

client = QdrantClient("http://qdrant:6333")

filter_a = models.Filter(must=[
    models.FieldCondition(key="grade", match=models.MatchValue(value=5)),
    models.FieldCondition(key="subject", match=models.MatchValue(value="maths")),
    models.FieldCondition(key="chapter", match=models.MatchValue(value="animal jumps")),
    models.FieldCondition(key="language", match=models.MatchValue(value="english"))
])

pts_a, _ = client.scroll("educational_chunks", scroll_filter=filter_a, limit=10)
print(f"A: {len(pts_a)}")

filter_b = models.Filter(must=[
    models.FieldCondition(key="chapter", match=models.MatchValue(value="animal jumps"))
])

pts_b, _ = client.scroll("educational_chunks", scroll_filter=filter_b, limit=10)
print(f"B: {len(pts_b)}")
