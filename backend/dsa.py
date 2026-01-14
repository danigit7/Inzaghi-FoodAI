from typing import List, Dict, Set
from models import Restaurant

class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.restaurant_ids = set()

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str, restaurant_id: str):
        node = self.root
        for char in word.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
            # Store ID at each node for prefix matching if we wanted instant results, 
            # but usually we just store at the end or collect during traversal.
            # Let's store at end for exact/prefix match.
        node.is_end_of_word = True
        node.restaurant_ids.add(restaurant_id)

    def search_prefix(self, prefix: str) -> Set[str]:
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return set()
            node = node.children[char]
        
        # Collect all IDs from this node downwards
        return self._collect_ids(node)

    def _collect_ids(self, node: TrieNode) -> Set[str]:
        ids = set()
        if node.is_end_of_word:
            ids.update(node.restaurant_ids)
        
        for child in node.children.values():
            ids.update(self._collect_ids(child))
        return ids

class InvertedIndex:
    def __init__(self):
        # Map menu item word -> Set of restaurant IDs
        self.index: Dict[str, Set[str]] = {}

    def add_restaurant(self, restaurant: Restaurant):
        for menu_item in restaurant.menu:
            # Simple tokenization: split by space
            words = menu_item.item.lower().split()
            for word in words:
                if word not in self.index:
                    self.index[word] = set()
                self.index[word].add(restaurant.id)

    def search(self, query: str) -> Set[str]:
        words = query.lower().split()
        if not words:
            return set()
        
        # Intersection of results for all words (AND query)
        # Or Union (OR query). Let's do OR for broader results, or AND for specific.
        # Let's start with OR for flexibility.
        result_ids = set()
        for word in words:
            if word in self.index:
                result_ids.update(self.index[word])
        return result_ids

    # ... (existing Trie and InvertedIndex classes)

class LocationIndex:
    def __init__(self):
        # Map location word -> Set of restaurant IDs
        self.index: Dict[str, Set[str]] = {}

    def add_restaurant(self, restaurant: Restaurant):
        if not restaurant.location:
            return
            
        # Tokenize by common delimiters (comma, space)
        # e.g. "Phase 2, Hayatabad" -> "phase", "2", "hayatabad"
        import re
        words = re.split(r'[,\s]+', restaurant.location.lower())
        for word in words:
            if not word: continue
            if word not in self.index:
                self.index[word] = set()
            self.index[word].add(restaurant.id)

    def search(self, query: str) -> Set[str]:
        words = query.lower().split()
        if not words:
            return set()
        
        # Filter for words that exist in the index to handle noise words gracefully
        valid_words = [w for w in words if w in self.index]
        
        if not valid_words:
            return set()
            
        # Start with the set of the first valid word
        result_ids = self.index[valid_words[0]].copy()
        
        # Intersect with the rest (AND logic)
        for word in valid_words[1:]:
            result_ids.intersection_update(self.index[word])
            
        return result_ids

class RestaurantManager:
    def __init__(self, restaurants: List[Restaurant]):
        self.restaurants = {r.id: r for r in restaurants}
        self.trie = Trie()
        self.menu_index = InvertedIndex()
        self.location_index = LocationIndex()
        self._build_indices()

    def _build_indices(self):
        for r in self.restaurants.values():
            # --- Data Normalization ---
            # Map 'category' to 'cuisine' if missing
            if not r.cuisine and r.category:
                r.cuisine = [c.strip() for c in r.category.split('/')]
            
            # Infer 'budget' from menu prices if missing
            if not r.budget and r.menu:
                avg_price = sum(m.price for m in r.menu) / len(r.menu)
                if avg_price < 600:
                    r.budget = "Street/Pocket-Friendly"
                elif avg_price < 1600:
                    r.budget = "Mid-Range"
                else:
                    r.budget = "Fine Dining/Premium"
            
            # Default location if missing (fallback)
            if not r.location:
                r.location = "Peshawar"

            # --- Indexing ---
            self.trie.insert(r.name, r.id)
            self.menu_index.add_restaurant(r)
            self.location_index.add_restaurant(r)

    def search_by_name(self, prefix: str) -> List[Restaurant]:
        ids = self.trie.search_prefix(prefix)
        return [self.restaurants[id] for id in ids]

    def search_by_menu(self, query: str) -> List[Restaurant]:
        ids = self.menu_index.search(query)
        return [self.restaurants[id] for id in ids]
        
    def search_by_location(self, query: str) -> List[Restaurant]:
        ids = self.location_index.search(query)
        return [self.restaurants[id] for id in ids]

    def filter_by_budget(self, budget: str) -> List[Restaurant]:
        return [r for r in self.restaurants.values() if r.budget.lower() == budget.lower()]

    def search_items_by_budget(self, max_price: int) -> List[dict]:
        """
        Finds specific menu items across all restaurants that are within the budget.
        Returns a list of dicts with restaurant info and the specific item.
        """
        results = []
        for r in self.restaurants.values():
            for item in r.menu:
                if item.price <= max_price:
                    results.append({
                        "restaurant": r,
                        "item": item
                    })
        # Sort by price descending (closest to budget)
        results.sort(key=lambda x: x['item'].price, reverse=True)
        return results

    def get_restaurant(self, id: str) -> Restaurant:
        return self.restaurants.get(id)
