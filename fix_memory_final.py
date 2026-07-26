# Write Memory.tsx completely using base64 to avoid any text mangling
import base64

# The correct Memory.tsx content
content = """import { useEffect, useState, FormEvent } from "react";
import { memory as memoryApi } from "@/lib/api";

interface MemoryItem {
  id: string;
  content: string;
  type: string;
  created_at: string;
}

export default function Memory() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Array<{ id: string; content: string; type: string; score: number }> | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadMemories();
  }, [page]);

  async function loadMemories() {
    setIsLoading(true);
    try {
      const limit = 20;
      const offset = (page - 1) * limit;
      const result = await memoryApi.getAll(limit, offset);
      setItems(result.items);
      setTotal(result.total);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    try {
      const results = await memoryApi.search(searchQuery);
      setSearchResults(results);
    } catch {
      // ignore
    }
  }

  async function handleDelete(id: string) {
    try {
      await memoryApi.delete(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
      setTotal((prev) => prev - 1);
    } catch {
      // ignore
    }
  }

  const displayedItems = searchResults || items;
  const totalPages = Math.ceil(total / 20);

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Memory</h2>
          <p className="page-subtitle">Search and manage your DASH memories</p>
        </div>

      <form onSubmit={handleSearch} style={{ marginBottom: 20, display: "flex", gap: 8 }}>
        <input
          className="input"
          type="text"
          placeholder="Search memories..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ maxWidth: 400 }}
        />
        <button type="submit" className="btn btn-primary">Search</button>
        {searchResults && (
          <button type="button" className="btn" onClick={() => { setSearchResults(null); setSearchQuery(""); }}>
            Clear
          </button>
        )}
      </form>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {isLoading && <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>Loading...</div>}
        {!isLoading && displayedItems.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
            {searchResults ? "No results found" : "No memories yet"}
          </div>
        )}
        {!isLoading && displayedItems.map((item, i) => (
          <div key={item.id} className="glass-card animate-fade-in" style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", animationDelay: `${i * 0.03}s` }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <span className="status-dot online" />
                <span style={{ fontSize: 12, color: "var(--accent-secondary)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  {item.type || "memory"}
                </span>
                {"score" in item && (
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    Score: {Math.round((item as any).score * 100)}%
                  </span>
                )}
              </div>
              <p style={{ fontSize: 14, color: "var(--text-primary)", lineHeight: 1.5 }}>{item.content}</p>
              {"created_at" in item && (
                <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>
                  {new Date((item as MemoryItem).created_at).toLocaleString()}
                </p>
              )}
            </div>
            <button className="btn-ghost" onClick={() => handleDelete(item.id)} style={{ padding: "4px 8px", fontSize: 12, color: "var(--danger)", flexShrink: 0 }}>
              Delete
            </button>
          </div>
        ))}
      </div>

      {!searchResults && totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 20 }}>
          <button className="btn" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</button>
          <span style={{ display: "flex", alignItems: "center", fontSize: 13, color: "var(--text-secondary)", padding: "0 12px" }}>
            Page {page} of {totalPages}
          </span>
          <button className="btn" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}
"""

# Encode to base64 to prevent any text processing issues
encoded = base64.b64encode(content.encode('utf-8')).decode('ascii')
print(f"Base64 length: {len(encoded)}")

# Write the encoded version
path = r'c:\Users\Asus\Desktop\dash\apps\desktop\src\pages\Memory.tsx'
with open(path + '.b64', 'w') as f:
    f.write(encoded)

print("Written Memory.tsx.b64 successfully")
