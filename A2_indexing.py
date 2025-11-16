import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import json
from pathlib import Path
from typing import List, Dict
import time


class JuliusCaesarIndexer:
    def __init__(
            self,
            chunks_path: str = "Data/julius_caesar_chunks.jsonl",
            db_path: str = "db",
            embedding_model: str = "BAAI/bge-base-en-v1.5",
            collection_name: str = "julius_caesar"
    ):
        self.chunks_path = Path(chunks_path)
        self.db_path = Path(db_path)
        self.embedding_model_name = embedding_model
        self.collection_name = collection_name

        self.embedding_model = SentenceTransformer(embedding_model)

        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

    def load_chunks(self) -> List[Dict]:
        if not self.chunks_path.exists():
            raise FileNotFoundError(f"Chunks file not found: {self.chunks_path}")

        chunks = []
        with open(self.chunks_path, 'r', encoding='utf-8') as f:
            for line in f:
                chunks.append(json.loads(line))

        print(f"Loaded {len(chunks)} chunks")
        return chunks

    def create_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        print(f"Creating embeddings for {len(texts)} chunks...")
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.embedding_model.encode(
                batch,
                show_progress_bar=False,
                normalize_embeddings=True
            )
            embeddings.extend(batch_embeddings.tolist())

        print(f"Created {len(embeddings)} embeddings")
        return embeddings

    def index_chunks(self, chunks: List[Dict], reset: bool = False):
        print(f"Indexing chunks into ChromaDB collection: '{self.collection_name}'")

        if reset:
            try:
                self.client.delete_collection(name=self.collection_name)
                print(f"Deleted existing collection")
            except:
                pass

        collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Julius Caesar play chunks for RAG"}
        )

        documents = []
        metadatas = []
        ids = []

        for chunk in chunks:
            chunk_id = str(chunk['chunk_id'])
            text = chunk['text']
            metadata = {
                'chunk_type': chunk['chunk_type'],
                'act': chunk['metadata'].get('act', 0),
                'scene': chunk['metadata'].get('scene', 0),
            }

            if chunk['chunk_type'] == 'scene':
                metadata['speakers'] = ','.join(chunk['metadata'].get('speakers', []))
                metadata['num_dialogues'] = chunk['metadata'].get('num_dialogues', 0)
                metadata['has_soliloquy'] = str(chunk['metadata'].get('has_soliloquy', False))
            elif chunk['chunk_type'] == 'soliloquy':
                metadata['speaker'] = chunk['metadata'].get('speaker', '')
                metadata['is_soliloquy'] = 'True'

            documents.append(text)
            metadatas.append(metadata)
            ids.append(chunk_id)

        embeddings = self.create_embeddings(documents)

        batch_size = 100
        print(f"Adding {len(documents)} chunks to ChromaDB...")

        for i in range(0, len(documents), batch_size):
            end_idx = min(i + batch_size, len(documents))

            collection.add(
                documents=documents[i:end_idx],
                embeddings=embeddings[i:end_idx],
                metadatas=metadatas[i:end_idx],
                ids=ids[i:end_idx]
            )

        print(f"Successfully indexed {len(documents)} chunks")
        count = collection.count()
        print(f"Collection now contains {count} chunks")

    def get_collection_stats(self) -> Dict:
        try:
            collection = self.client.get_collection(name=self.collection_name)
            all_data = collection.get(include=['metadatas'])
            metadatas = all_data['metadatas']

            stats = {
                'total_chunks': len(metadatas),
                'scene_chunks': sum(1 for m in metadatas if m.get('chunk_type') == 'scene'),
                'soliloquy_chunks': sum(1 for m in metadatas if m.get('chunk_type') == 'soliloquy'),
                'acts_covered': sorted(set(m.get('act', 0) for m in metadatas if m.get('act'))),
                'unique_scenes': len(set((m.get('act', 0), m.get('scene', 0))
                                         for m in metadatas if m.get('act') and m.get('scene')))
            }

            return stats
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}

    def search(
            self,
            query: str,
            n_results: int = 5,
            filter_act: int = None,
            filter_scene: int = None,
            filter_type: str = None
    ) -> List[Dict]:
        try:
            collection = self.client.get_collection(name=self.collection_name)

            where_filter = {}
            if filter_act is not None:
                where_filter['act'] = filter_act
            if filter_scene is not None:
                where_filter['scene'] = filter_scene
            if filter_type is not None:
                where_filter['chunk_type'] = filter_type

            query_embedding = self.embedding_model.encode(
                [query],
                normalize_embeddings=True
            )[0].tolist()

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter if where_filter else None,
                include=['documents', 'metadatas', 'distances']
            )

            formatted_results = []
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i],
                    'similarity': 1 - results['distances'][0][i]
                })

            return formatted_results

        except Exception as e:
            print(f"Search error: {e}")
            return []

    def test_search(self):
        print("\nTESTING SEARCH FUNCTIONALITY")

        test_queries = [
            "What does Brutus think about Caesar?",
            "Beware the ides of March",
            "Et tu, Brute?",
            "Antony's funeral speech",
            "Portia's concern for Brutus"
        ]

        for query in test_queries:
            print(f"\nQuery: '{query}'")
            print("-" * 60)

            results = self.search(query, n_results=3)

            for i, result in enumerate(results, 1):
                metadata = result['metadata']
                similarity = result['similarity']
                preview = result['document'][:200] + "..." if len(result['document']) > 200 else result['document']

                print(f"\n{i}. [Similarity: {similarity:.3f}] Act {metadata.get('act')}, Scene {metadata.get('scene')}")
                print(f"   Type: {metadata.get('chunk_type')}")
                if metadata.get('speaker'):
                    print(f"   Speaker: {metadata.get('speaker')}")
                print(f"   Preview: {preview}")

    def run_full_indexing(self, reset: bool = True):
        print("\nJULIUS CAESAR - INDEXING PIPELINE")
        start_time = time.time()

        chunks = self.load_chunks()
        self.index_chunks(chunks, reset=reset)
        stats = self.get_collection_stats()
        end_time = time.time()

        print("\nINDEXING COMPLETED!")
        print(f"\nCollection Statistics:")
        print(f"   - Total chunks: {stats.get('total_chunks', 0)}")
        print(f"   - Scene chunks: {stats.get('scene_chunks', 0)}")
        print(f"   - Soliloquy chunks: {stats.get('soliloquy_chunks', 0)}")
        print(f"   - Acts covered: {stats.get('acts_covered', [])}")
        print(f"   - Unique scenes: {stats.get('unique_scenes', 0)}")
        print(f"\nTotal time: {end_time - start_time:.2f} seconds")
        print(f"\nDatabase persisted at: {self.db_path}")


def main():
    CHUNKS_PATH = "Data/julius_caesar_chunks.jsonl"
    DB_PATH = "db"
    EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

    print("\nChoose an option:")
    print("1. Index chunks (fresh start - deletes existing)")
    print("2. Index chunks (add to existing)")
    print("3. Test search functionality")
    print("4. Show collection statistics")
    print("5. Run full pipeline + test search")

    choice = input("\nEnter choice (1/2/3/4/5): ").strip()

    indexer = JuliusCaesarIndexer(
        chunks_path=CHUNKS_PATH,
        db_path=DB_PATH,
        embedding_model=EMBEDDING_MODEL
    )

    if choice == '1':
        chunks = indexer.load_chunks()
        indexer.index_chunks(chunks, reset=True)
        stats = indexer.get_collection_stats()
        print(f"\nStats: {stats}")

    elif choice == '2':
        chunks = indexer.load_chunks()
        indexer.index_chunks(chunks, reset=False)
        stats = indexer.get_collection_stats()
        print(f"\nStats: {stats}")

    elif choice == '3':
        indexer.test_search()

    elif choice == '4':
        stats = indexer.get_collection_stats()
        print(f"\nCollection Statistics:")
        for key, value in stats.items():
            print(f"   - {key}: {value}")

    elif choice == '5':
        indexer.run_full_indexing(reset=True)
        print("\n" + "=" * 60)
        input("Press Enter to run search tests...")
        indexer.test_search()

    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()