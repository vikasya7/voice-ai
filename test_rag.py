from app.rag.knowledge import get_retriever
from dotenv import load_dotenv


load_dotenv()
retriever = get_retriever()

docs = retriever.invoke(
    "What are your opening hours?"
)

for doc in docs:
    print("\n--- DOCUMENT ---")
    print(doc.page_content)