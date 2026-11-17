import asyncio
import re
from app.agents.retriever import retrieve

async def test():
    q = "What is the 1-year fixed deposit interest rate?"
    ev = await retrieve(q)
    print("Retrieved chunks:", len(ev))

    docs = {}
    for e in ev:
        t = e.get("document_title")
        if t and "Priority Document" not in t:
            docs.setdefault(t, []).append(e)

    print("Distinct docs in evidence:", list(docs.keys()))
    for title, chunks in docs.items():
        all_text = " ".join(c.get("content", "") for c in chunks)
        # Search for lines containing 1 year or 1-2 years
        matches = re.findall(r'(?:1\s*year|1-2\s*years)[^\n]*', all_text, re.I)
        print(f"\nDocument '{title}':")
        for m in matches[:3]:
            print("  •", m.strip())

if __name__ == "__main__":
    asyncio.run(test())
