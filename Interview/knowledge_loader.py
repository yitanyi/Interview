from pathlib import Path
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Cache split chunks by (paths + mtimes) to speed up repeated session starts.
_KB_CHUNKS_CACHE = {}

# 修改后：
def load_knowledge_base(file_paths):
    """加载多个知识库文件并切分成块"""
    documents = []
    # 获取项目根目录（knowledge_loader.py 所在目录）
    base_dir = Path(__file__).parent.resolve()

    # Build a stable cache key from absolute paths + mtimes.
    resolved = []
    for p in file_paths or []:
        try:
            pp = p if isinstance(p, Path) else Path(p)
            if not pp.is_absolute():
                pp = base_dir / pp
            if pp.exists():
                resolved.append(f"{pp.resolve()}@{pp.stat().st_mtime_ns}")
            else:
                resolved.append(str(pp))
        except Exception:
            continue
    cache_key = "|".join(sorted(resolved))
    if cache_key and cache_key in _KB_CHUNKS_CACHE:
        return _KB_CHUNKS_CACHE[cache_key]
    
    for path in file_paths:
        # 如果是相对路径，转换为绝对路径
        if not isinstance(path, Path):
            path = Path(path)
        if not path.is_absolute():
            path = base_dir / path
            
        if not path.exists():
            print(f"警告：知识库文件不存在 {path}")
            continue
        loader = UnstructuredMarkdownLoader(str(path))
        docs = loader.load()
        documents.extend(docs)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(documents)

    if cache_key:
        _KB_CHUNKS_CACHE[cache_key] = chunks
    return chunks
