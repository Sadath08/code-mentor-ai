"""
knowledge_base/build_kb.py
---------------------------
Build the FAISS index from a curated set of coding knowledge chunks.
Run once: python knowledge_base/build_kb.py
The resulting index is saved to ./faiss_index for the RAG service.
"""
from __future__ import annotations
import json
import os
import sys
import asyncio
import logging
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE BASE CHUNKS (~60 entries for a hackathon demo)
# Each chunk: {language, concept, text}
# ─────────────────────────────────────────────────────────────────────────────
CHUNKS = [
    # ── Python Fundamentals ──────────────────────────────────────────────────
    {"language": "python", "concept": "syntax_error", "text": "Python uses indentation instead of braces. Every block (if, for, while, def, class) must be consistently indented. A mismatch causes IndentationError. Use 4 spaces, not tabs. if condition:\n    do_something()  # Must be indented"},
    {"language": "python", "concept": "syntax_error", "text": "Colon (:) is required at the end of if/else/for/while/def/class statements. Missing colon is the most common Python syntax error. Correct: if x > 5:"},
    {"language": "python", "concept": "variables", "text": "Python variables are dynamically typed. Never declare type explicitly. x = 10 is fine. Common beginner mistake: using = for comparison (should be ==). Assignment: x = 5. Comparison: if x == 5."},
    {"language": "python", "concept": "strings", "text": "Common string errors: (1) using + to concatenate mixed types: str(x) + ' items'. (2) Off-by-one in slicing: s[0:5] gives 5 chars. (3) Strings are immutable; you cannot do s[0] = 'A'. Use s.replace() or rebuild."},
    {"language": "python", "concept": "type_error", "text": "TypeError occurs when you apply an operation to wrong type. Common: int + str (use str(n) to convert), calling non-callable, indexing non-sequence. Always validate input types before operations."},

    # ── Python Recursion ──────────────────────────────────────────────────────
    {"language": "python", "concept": "recursion", "text": "RECURSION FUNDAMENTALS: Every recursive function needs (1) a base case that stops recursion, (2) a recursive case that calls itself with a smaller input. Missing base case leads to infinite recursion and RecursionError.\ndef factorial(n):\n    if n <= 1: return 1  # base case\n    return n * factorial(n-1)  # recursive case moves toward base"},
    {"language": "python", "concept": "recursion", "text": "RECURSION COMMON MISTAKES: (1) Forgetting return in recursive branch. (2) Base case condition wrong (e.g., n == 0 instead of n <= 1). (3) Not reducing problem size on each call. (4) Stack overflow from too-deep recursion; use iterative solution or memoization for large n."},
    {"language": "python", "concept": "recursion", "text": "MEMOIZATION: Cache recursive call results to avoid recomputation. Use @functools.lru_cache or a dict. Transforms exponential O(2^n) time to O(n). from functools import lru_cache\n@lru_cache(maxsize=None)\ndef fib(n): return n if n < 2 else fib(n-1)+fib(n-2)"},
    {"language": "general", "concept": "recursion", "text": "Recursion vs Iteration: Recursion is elegant but has function call overhead and stack risk. Prefer iteration for simple loops. Use recursion for tree/graph traversal, divide-and-conquer, backtracking. Always analyze if tail-call or memoization is needed."},

    # ── Python Loops ─────────────────────────────────────────────────────────
    {"language": "python", "concept": "loops", "text": "OFF-BY-ONE ERRORS: range(n) goes 0 to n-1 (n elements). range(1, n+1) goes 1 to n. Accessing arr[len(arr)] causes IndexError. Use range(len(arr)) for index-based iteration. Better: for item in arr (no index needed)."},
    {"language": "python", "concept": "loops", "text": "LOOP BEST PRACTICES: (1) Prefer enumerate() over manual index: for i, v in enumerate(lst). (2) Prefer zip() to iterate two lists: for a, b in zip(list1, list2). (3) Never modify a list while iterating it. (4) Use break and continue mindfully."},
    {"language": "python", "concept": "loops", "text": "INFINITE LOOPS: while loops must have a termination condition. Always ensure the loop variable is updated inside the body. Common bug: condition never becomes False because variable is not modified inside loop."},
    {"language": "python", "concept": "loops", "text": "NESTED LOOPS OPTIMIZATION: Two nested loops = O(n^2). Consider: (1) HashMap/dict: replace inner loop with O(1) lookup. (2) Sorting + two pointers. (3) Sliding window. Example (Two Sum): instead of O(n^2) nested loops, use a dict for O(n)."},

    # ── Python Data Structures ────────────────────────────────────────────────
    {"language": "python", "concept": "arrays", "text": "LIST OPERATIONS: append O(1), insert O(n), pop() O(1), pop(i) O(n), in-operator O(n), index O(n). Use deque for O(1) popleft. List comprehension is faster than for-loop append. sorted() returns new list; list.sort() sorts in-place."},
    {"language": "python", "concept": "arrays", "text": "COMMON LIST BUGS: (1) Shallow copy bug: b = a makes both point to same list, use b = a.copy(). (2) Empty list check: use 'if lst:' not 'if len(lst) > 0'. (3) Negative index: lst[-1] = last element (valid). (4) Slicing creates a copy; assignment to slice modifies in-place."},
    {"language": "python", "concept": "dictionaries", "text": "DICT BEST PRACTICES: Use .get(key, default) to avoid KeyError. Use dict comprehension. collections.defaultdict avoids key initialization. Counter for frequency counting. Check 'if key in d' before accessing. Python 3.7+ dicts are ordered by default."},
    {"language": "general", "concept": "stacks", "text": "STACK (LIFO): Last-In-First-Out. Operations: push (append), pop (pop), peek ([-1]). Use cases: balanced parentheses, function call stack, undo operations, DFS. In Python: use list as stack. Time: O(1) push/pop."},
    {"language": "general", "concept": "queues", "text": "QUEUE (FIFO): First-In-First-Out. Use collections.deque in Python for O(1) append and popleft. Use cases: BFS, scheduling, print queues. Never use list for queue (pop(0) is O(n))."},

    # ── Algorithms ───────────────────────────────────────────────────────────
    {"language": "general", "concept": "binary_search", "text": "BINARY SEARCH: Only works on sorted arrays. Time: O(log n). Template: lo, hi = 0, len(arr)-1; while lo<=hi: mid=(lo+hi)//2; if arr[mid]==target: return mid; elif arr[mid]<target: lo=mid+1; else: hi=mid-1. Common bug: lo+hi overflow (use lo+(hi-lo)//2 in other languages)."},
    {"language": "general", "concept": "sorting", "text": "SORTING COMPLEXITY: Bubble/Selection/Insertion: O(n^2). Merge/Heap: O(n log n). Quick: O(n log n) avg, O(n^2) worst. Python's sorted() uses TimSort O(n log n). For nearly sorted data, insertion sort is efficient. Use key= parameter for custom sort."},
    {"language": "general", "concept": "dynamic_programming", "text": "DYNAMIC PROGRAMMING: Solve overlapping subproblems. Two approaches: (1) Top-down with memoization (recursive + cache). (2) Bottom-up with tabulation (iterative + dp array). Identify: optimal substructure + overlapping subproblems. Classic problems: Fibonacci, knapsack, LCS, coin change."},
    {"language": "general", "concept": "two_pointers", "text": "TWO POINTER TECHNIQUE: Use two indices to traverse array. Reduces O(n^2) to O(n). Patterns: (1) Left+right moving toward center (palindrome check, container with water). (2) Slow+fast pointers (cycle detection). (3) Both starting from left at different speeds (sliding window)."},

    # ── Clean Code ───────────────────────────────────────────────────────────
    {"language": "general", "concept": "naming_issue", "text": "NAMING CONVENTIONS: Variables/functions: snake_case. Classes: PascalCase. Constants: UPPER_CASE. Bad: x, tmp, data2, fn. Good: user_count, is_valid, calculate_area. Names should be self-documenting. Avoid single-letter variables except loop indices (i, j, k)."},
    {"language": "general", "concept": "code_complexity", "text": "REDUCING COMPLEXITY: (1) Extract repeated code into functions. (2) Limit nesting to 3 levels max. (3) Single Responsibility Principle. (4) Replace complex conditionals with guard clauses (early returns). (5) Use meaningful names to eliminate comments. (6) Keep functions under 20 lines."},
    {"language": "python", "concept": "performance", "text": "PYTHON PERFORMANCE TIPS: (1) Use list comprehension over for-loop. (2) Use sets for O(1) lookup instead of list. (3) Use join() for string concatenation, not +. (4) Use generators for large data. (5) Avoid global variables in loops. (6) Profile before optimizing."},

    # ── Python OOP ───────────────────────────────────────────────────────────
    {"language": "python", "concept": "object_oriented_programming", "text": "PYTHON OOP: (1) __init__ is the constructor. (2) self must be the first parameter of all methods. (3) Use @property for getters. (4) Inheritance: class Child(Parent). (5) super().__init__() calls parent constructor. (6) @staticmethod and @classmethod for class-level methods."},
    {"language": "python", "concept": "object_oriented_programming", "text": "OOP COMMON ERRORS: (1) Mutable default argument: def __init__(self, items=[]). Use items=None then items=[] inside. (2) Forgetting self in method call: self.method(). (3) Not calling super().__init__(). (4) Confusing class variables (shared) with instance variables (per-object)."},

    # ── Python Error Handling ─────────────────────────────────────────────────
    {"language": "python", "concept": "runtime_error", "text": "EXCEPTION HANDLING: Use specific exceptions not bare except. try/except/else/finally pattern. Raise custom exceptions with raise ValueError('message'). Log exceptions; do not swallow them. ZeroDivisionError, IndexError, KeyError, ValueError, TypeError are the most common in interviews."},
    {"language": "python", "concept": "runtime_error", "text": "NONE HANDLING: NoneType has no attributes/methods. Always check 'if result is not None' before using. Functions that do not explicitly return a value return None. Common: s = some_function() then s.upper() causes AttributeError if s is None."},

    # ── JavaScript Fundamentals ───────────────────────────────────────────────
    {"language": "javascript", "concept": "async_await", "text": "JAVASCRIPT ASYNC/AWAIT: async functions always return a Promise. Use await inside async functions to pause execution. Common mistake: forgetting await causes a Promise object instead of the resolved value. Always wrap await in try/catch for error handling.\nasync function fetchData() {\n  try {\n    const data = await fetch(url).then(r => r.json());\n    return data;\n  } catch (err) { console.error(err); }\n}"},
    {"language": "javascript", "concept": "closures", "text": "JAVASCRIPT CLOSURES: A closure is a function that remembers variables from its outer scope even after the outer function returns. Common bug: using var in loops creates one shared binding. Fix: use let (block-scoped) or an IIFE.\n// Bug: all callbacks log 3\nfor (var i=0; i<3; i++) setTimeout(()=>console.log(i), 0);\n// Fix: use let\nfor (let i=0; i<3; i++) setTimeout(()=>console.log(i), 0);"},
    {"language": "javascript", "concept": "type_error", "text": "JAVASCRIPT TYPE COERCION: JS silently converts types. '5' + 3 = '53' (string concat). '5' - 3 = 2 (numeric). Use === (strict equality) not == (loose). typeof null === 'object' is a historical bug. Always use === and check types explicitly. undefined !== null but both are falsy."},
    {"language": "javascript", "concept": "prototype", "text": "JAVASCRIPT PROTOTYPE CHAIN: Every object has a __proto__ link to its prototype. Property lookup walks the chain until null. class syntax is syntactic sugar over prototype-based inheritance. Common mistake: arrow functions do not have their own 'this'; use regular functions for methods. this inside a callback can be unexpected; use .bind(this) or arrow functions."},
    {"language": "javascript", "concept": "dom_bugs", "text": "COMMON DOM BUGS: (1) querySelector returns null if element not found; always null-check. (2) Event listeners not removed cause memory leaks; use removeEventListener. (3) innerHTML with user input causes XSS; use textContent instead. (4) Modifying DOM inside a loop is slow; batch changes with DocumentFragment."},
    {"language": "javascript", "concept": "arrays", "text": "JAVASCRIPT ARRAY METHODS: map() transforms, filter() selects, reduce() accumulates. All return new arrays (immutable pattern). forEach() has no return value. find() returns first match or undefined. includes() for membership. splice() mutates in place; slice() does not. Use spread [...arr] for shallow copy."},

    # ── Java Fundamentals ────────────────────────────────────────────────────
    {"language": "java", "concept": "runtime_error", "text": "JAVA NULLPOINTEREXCEPTION: NullPointerException (NPE) is the most common Java error. Occurs when you call a method or access a field on a null object. Fix: (1) Always initialize objects before use. (2) Use Optional<T> for values that may be absent. (3) Check 'if (obj != null)' before use. Java 14+ provides helpful NPE messages showing exactly which variable is null."},
    {"language": "java", "concept": "object_oriented_programming", "text": "JAVA OOP PILLARS: (1) Encapsulation: private fields + public getters/setters. (2) Inheritance: class Dog extends Animal. (3) Polymorphism: method overriding (@Override) and overloading. (4) Abstraction: abstract classes and interfaces. Use interface for contracts, abstract class for shared behavior. Java supports single class inheritance but multiple interface implementation."},
    {"language": "java", "concept": "generics", "text": "JAVA GENERICS: Generics provide type safety at compile time. List<String> only holds Strings. Generic method: <T> T identity(T val). Bounded wildcards: <? extends Number> (read-only), <? super Integer> (write). Common mistake: List<Dog> is NOT a subtype of List<Animal>. Use List<? extends Animal> for covariance."},
    {"language": "java", "concept": "arrays", "text": "JAVA COLLECTIONS: ArrayList (dynamic array), LinkedList (doubly-linked), HashMap (O(1) get/put), TreeMap (sorted, O(log n)), HashSet (unique elements). Use Collections.sort() or list.sort(). CopyOnWriteArrayList for thread-safe reads. Always program to interface: List<String> list = new ArrayList<>()."},
    {"language": "java", "concept": "performance", "text": "JAVA STRINGS: String is immutable. Concatenation in a loop creates many objects. Use StringBuilder for mutable string building. String.equals() for content comparison (never == for strings). String.format() or printf for formatting. String pool: string literals are interned; new String() is not."},

    # ── C++ Fundamentals ─────────────────────────────────────────────────────
    {"language": "cpp", "concept": "runtime_error", "text": "C++ POINTERS AND REFERENCES: Pointer holds a memory address; reference is an alias. int* ptr = &x; *ptr = 5; dereferences. Never dereference a null or dangling pointer (undefined behavior). Prefer references over pointers when possible. Use smart pointers (unique_ptr, shared_ptr) to avoid manual memory management."},
    {"language": "cpp", "concept": "runtime_error", "text": "C++ MEMORY MANAGEMENT: new allocates on heap; delete frees. new[] for arrays; delete[] to free. Forgetting delete causes memory leaks. Double delete causes undefined behavior. Rule of Three/Five: if you define destructor, copy constructor, or copy assignment, define all. Prefer RAII and smart pointers."},
    {"language": "cpp", "concept": "arrays", "text": "C++ STL CONTAINERS: vector (dynamic array), deque, list (doubly-linked), map (BST, ordered), unordered_map (hash, O(1)), set, priority_queue. Use vector over raw arrays. auto with iterators: for (auto& x : vec). sort(vec.begin(), vec.end()). Use emplace_back() over push_back() for in-place construction."},
    {"language": "cpp", "concept": "performance", "text": "C++ COMMON BUGS: (1) Off-by-one in loops and array access. (2) Integer overflow: use long long for large values. (3) Comparing signed and unsigned integers causes warnings and bugs. (4) Uninitialized variables have garbage values. (5) endl flushes buffer and is slow; use '\\n'. (6) Forgetting break in switch falls through to next case."},

    # ── DSA Deep-Dive: Graphs ────────────────────────────────────────────────
    {"language": "general", "concept": "graphs", "text": "GRAPH BFS (Breadth-First Search): Explores nodes level by level. Uses a queue. Good for: shortest path in unweighted graphs, level-order traversal. Time: O(V+E). Template:\nfrom collections import deque\ndef bfs(graph, start):\n    visited = {start}\n    queue = deque([start])\n    while queue:\n        node = queue.popleft()\n        for neighbor in graph[node]:\n            if neighbor not in visited:\n                visited.add(neighbor)\n                queue.append(neighbor)"},
    {"language": "general", "concept": "graphs", "text": "GRAPH DFS (Depth-First Search): Explores as deep as possible before backtracking. Uses stack (or recursion). Good for: detecting cycles, topological sort, connected components, maze solving. Time: O(V+E). Common bug: forgetting to mark node as visited before recursing (causes infinite loops in cyclic graphs)."},
    {"language": "general", "concept": "graphs", "text": "GRAPH REPRESENTATIONS: (1) Adjacency List: dict/list of lists. Space O(V+E). Best for sparse graphs. (2) Adjacency Matrix: 2D array. Space O(V^2). Fast edge lookup O(1). Best for dense graphs. Directed vs Undirected: undirected adds edges both ways. Weighted: store (neighbor, weight) tuples in adjacency list."},

    # ── DSA Deep-Dive: Trees ─────────────────────────────────────────────────
    {"language": "general", "concept": "trees", "text": "BINARY TREE TRAVERSALS: In-order (L-Root-R): gives sorted sequence for BST. Pre-order (Root-L-R): used to copy/serialize tree. Post-order (L-R-Root): used to delete tree. Level-order: BFS with queue. Recursive traversals are clean; use iterative with explicit stack to avoid recursion depth issues."},
    {"language": "general", "concept": "trees", "text": "BINARY SEARCH TREE (BST): Left child < parent < right child. Operations: search O(h), insert O(h), delete O(h) where h=height. Balanced BST height: O(log n). Unbalanced worst case: O(n). Self-balancing: AVL tree, Red-Black tree. Python: use sortedcontainers.SortedList. Java: TreeMap. C++: std::map."},
    {"language": "general", "concept": "trees", "text": "COMMON TREE PROBLEMS: (1) Height of tree: 1 + max(height(left), height(right)); base case: return 0 if None. (2) Check balanced: abs(height(left) - height(right)) <= 1 at every node. (3) Lowest Common Ancestor: traverse from root; if both p and q are on different sides, current node is LCA. (4) Path sum: DFS subtracting target along the way."},

    # ── DSA Deep-Dive: Heaps & Advanced ──────────────────────────────────────
    {"language": "general", "concept": "heaps", "text": "HEAP / PRIORITY QUEUE: Min-heap: smallest element at top. Max-heap: negate values in Python (heapq is min-heap only). Operations: heappush O(log n), heappop O(log n), heapify O(n). Use cases: Dijkstra's algorithm, K largest/smallest elements, merge K sorted lists, task scheduling. import heapq in Python."},
    {"language": "general", "concept": "union_find", "text": "UNION-FIND (Disjoint Set Union): Tracks connected components. find(x): returns root with path compression. union(x, y): merges two sets by rank. Both operations nearly O(1) amortized. Use cases: Kruskal's MST, detecting cycles in undirected graph, number of connected components, network connectivity."},
    {"language": "general", "concept": "trie", "text": "TRIE (Prefix Tree): Tree where each node represents a character. Used for: autocomplete, spell checking, prefix search. Insert and search are O(L) where L=word length. Space: O(ALPHABET_SIZE x L x N). Implementation: dict of dicts or TrieNode class with children dict and is_end boolean flag."},
    {"language": "general", "concept": "sliding_window", "text": "SLIDING WINDOW TECHNIQUE: Maintain a window [left, right] that expands/contracts. Avoids redundant recomputation of subarray sums/max/min. Two types: (1) Fixed size: move both pointers by 1. (2) Variable size: expand right until condition violated, shrink left. Common problems: max sum subarray of size k, longest substring without repeating characters."},

    # ── System Design Basics ─────────────────────────────────────────────────
    {"language": "general", "concept": "system_design", "text": "CACHING STRATEGIES: (1) Cache-aside: app checks cache first, loads from DB on miss, writes to cache. (2) Write-through: write to cache and DB simultaneously. (3) Write-back: write to cache, async flush to DB. Eviction policies: LRU (Least Recently Used), LFU (Least Frequently Used), TTL expiry. Redis and Memcached are popular choices."},
    {"language": "general", "concept": "system_design", "text": "RATE LIMITING ALGORITHMS: (1) Token Bucket: tokens added at fixed rate; request consumes a token. (2) Leaky Bucket: requests processed at fixed rate; overflow dropped. (3) Sliding Window Counter: count requests in recent time window. (4) Fixed Window Counter: simplest; resets every interval. Rate limit on: IP, user ID, API key."},
    {"language": "general", "concept": "system_design", "text": "LOAD BALANCING: Distributes traffic across servers. Algorithms: Round Robin (even distribution), Least Connections (send to least busy), IP Hash (sticky sessions), Weighted Round Robin. Layer 4 (TCP) vs Layer 7 (HTTP/application-aware). Health checks remove failed servers automatically. Popular: Nginx, HAProxy, AWS ALB."},
    {"language": "general", "concept": "system_design", "text": "DATABASE SCALING: Vertical scaling (bigger server) has limits. Horizontal scaling: (1) Replication: primary writes, replicas read. (2) Sharding: partition data across multiple DBs by key. CAP theorem: Consistency, Availability, Partition Tolerance; pick two. SQL: ACID transactions. NoSQL: eventual consistency, flexible schema, horizontal scale."},
]


async def build_index():
    """Build and save the FAISS index."""
    try:
        import faiss
        import numpy as np
    except ImportError:
        logger.error("faiss or numpy not installed. Run: pip install faiss-cpu numpy")
        return

    import google.generativeai as genai
    from app.config import get_settings

    settings = get_settings()
    if not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here":
        logger.error("GEMINI_API_KEY not set in .env file.")
        return

    genai.configure(api_key=settings.gemini_api_key)

    logger.info("Embedding %d knowledge chunks...", len(CHUNKS))
    texts = [c["text"] for c in CHUNKS]

    # Batch embed (max 100 per API call)
    vectors = []
    BATCH_SIZE = 50
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        response = await asyncio.to_thread(
            genai.embed_content,
            model=settings.embedding_model,
            content=batch,
            task_type="retrieval_document"
        )
        vectors.extend(response['embedding'])
        logger.info("Embedded %d/%d chunks", min(i + BATCH_SIZE, len(texts)), len(texts))

    # L2-normalize vectors for cosine similarity
    matrix = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    matrix = (matrix / norms).astype(np.float32)

    # Build FAISS IndexFlatIP (Cosine Similarity)
    dim = matrix.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(matrix)

    # Save index and metadata
    index_dir = Path(settings.faiss_index_path).parent
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, settings.faiss_index_path)

    meta_path = index_dir / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(CHUNKS, f, indent=2)

    logger.info(
        "✅ FAISS index built with %d vectors → %s",
        index.ntotal,
        settings.faiss_index_path,
    )


if __name__ == "__main__":
    asyncio.run(build_index())
