from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]

KNOWLEDGE_FILE = BASE_DIR / "knowledge" / "buisness_info.txt"
VECTORSTORE_DIR = BASE_DIR / "knowledge" / "faiss_index"


embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small"
)


def create_vectorstore():
    print("Creating FAISS vector store...")

    loader = TextLoader(
        str(KNOWLEDGE_FILE)
    )

    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )

    chunks = splitter.split_documents(documents)

    vectorstore = FAISS.from_documents(
        chunks,
        embeddings
    )

    vectorstore.save_local(
        str(VECTORSTORE_DIR)
    )

    print("FAISS vector store created.")

    return vectorstore


def get_vectorstore():

    if VECTORSTORE_DIR.exists():
        print("Loading existing FAISS vector store...")

        return FAISS.load_local(
            str(VECTORSTORE_DIR),
            embeddings,
            allow_dangerous_deserialization=True
        )

    return create_vectorstore()


def get_retriever():

    vectorstore = get_vectorstore()

    return vectorstore.as_retriever(
        search_kwargs={
            "k": 3
        }
    )