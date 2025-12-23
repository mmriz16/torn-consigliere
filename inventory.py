"""
Inventory Module for Torn City
Displays user inventory with item details, quantities, and market prices.
"""

import requests
import json
from typing import Dict, List, Optional
from datetime import datetime
from tabulate import tabulate


class InventoryManager:
    """Manages and displays user inventory information from Torn City API."""
    
    def __init__(self, api_key: str):
        """
        Initialize the InventoryManager with API credentials.
        
        Args:
            api_key (str): Torn City API key for authentication
        """
        self.api_key = api_key
        self.base_url = "https://api.torn.com"
        self.items_cache = {}
        self.market_cache = {}
    
    def get_inventory(self) -> Optional[Dict]:
        """
        Fetch user's inventory from Torn City API.
        
        Returns:
            Optional[Dict]: User's inventory data or None if request fails
        """
        try:
            endpoint = f"{self.base_url}/user/?selections=inventory&key={self.api_key}"
            response = requests.get(endpoint, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                print(f"API Error: {data['error']['error']}")
                return None
            
            return data.get("inventory", {})
        
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch inventory: {e}")
            return None
    
    def get_item_details(self, item_id: int) -> Optional[Dict]:
        """
        Fetch details for a specific item.
        
        Args:
            item_id (int): The item ID to fetch details for
            
        Returns:
            Optional[Dict]: Item details or None if request fails
        """
        if item_id in self.items_cache:
            return self.items_cache[item_id]
        
        try:
            endpoint = f"{self.base_url}/item/{item_id}?key={self.api_key}"
            response = requests.get(endpoint, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "error" not in data:
                self.items_cache[item_id] = data
                return data
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch item {item_id} details: {e}")
        
        return None
    
    def get_market_price(self, item_id: int) -> Optional[float]:
        """
        Fetch current market price for an item.
        
        Args:
            item_id (int): The item ID to fetch market price for
            
        Returns:
            Optional[float]: Market price or None if unavailable
        """
        if item_id in self.market_cache:
            return self.market_cache[item_id]
        
        try:
            endpoint = f"{self.base_url}/market/?selections=bazaar&key={self.api_key}"
            response = requests.get(endpoint, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "bazaar" in data:
                for listing in data["bazaar"]:
                    if listing.get("item_id") == item_id:
                        price = listing.get("cost", 0)
                        self.market_cache[item_id] = price
                        return price
        
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch market price for item {item_id}: {e}")
        
        return None
    
    def display_inventory(self, sort_by: str = "name", reverse: bool = False) -> None:
        """
        Fetch and display user's inventory in a formatted table.
        
        Args:
            sort_by (str): Column to sort by ('name', 'quantity', 'price', 'total_value')
            reverse (bool): Sort in reverse order
        """
        inventory = self.get_inventory()
        
        if not inventory:
            print("No inventory data available or inventory is empty.")
            return
        
        inventory_data = []
        
        for item_id, quantity in inventory.items():
            item_id = int(item_id)
            details = self.get_item_details(item_id)
            market_price = self.get_market_price(item_id)
            
            item_name = details.get("name", f"Item {item_id}") if details else f"Item {item_id}"
            item_type = details.get("type", "Unknown") if details else "Unknown"
            description = details.get("description", "N/A") if details else "N/A"
            market_price = market_price or 0
            total_value = quantity * market_price
            
            inventory_data.append({
                "Item ID": item_id,
                "Name": item_name,
                "Type": item_type,
                "Quantity": quantity,
                "Market Price": f"${market_price:,.2f}",
                "Total Value": f"${total_value:,.2f}",
                "Description": description[:40] + "..." if len(description) > 40 else description
            })
        
        if not inventory_data:
            print("Inventory is empty.")
            return
        
        # Sort the data
        sort_keys = {
            "name": "Name",
            "quantity": "Quantity",
            "price": "Market Price",
            "total_value": "Total Value",
            "type": "Type"
        }
        
        sort_key = sort_keys.get(sort_by, "Name")
        
        # Handle numeric sorting for price and quantity columns
        if sort_key in ["Quantity", "Market Price", "Total Value"]:
            if sort_key == "Quantity":
                inventory_data.sort(key=lambda x: x[sort_key], reverse=reverse)
            else:
                inventory_data.sort(
                    key=lambda x: float(x[sort_key].replace("$", "").replace(",", "")),
                    reverse=reverse
                )
        else:
            inventory_data.sort(key=lambda x: x[sort_key], reverse=reverse)
        
        # Display the table
        print("\n" + "="*120)
        print(f"User Inventory - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("="*120 + "\n")
        
        headers = ["Item ID", "Name", "Type", "Quantity", "Market Price", "Total Value", "Description"]
        print(tabulate(inventory_data, headers=headers, tablefmt="grid"))
        
        # Calculate and display summary
        total_inventory_value = sum(
            int(item["Quantity"]) * float(item["Market Price"].replace("$", "").replace(",", ""))
            for item in inventory_data
        )
        
        print("\n" + "="*120)
        print(f"Total Inventory Value: ${total_inventory_value:,.2f}")
        print(f"Total Items: {sum(item['Quantity'] for item in inventory_data)}")
        print(f"Unique Items: {len(inventory_data)}")
        print("="*120 + "\n")
    
    def export_inventory_json(self, filename: str = "inventory.json") -> bool:
        """
        Export inventory data to a JSON file.
        
        Args:
            filename (str): Name of the output JSON file
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        inventory = self.get_inventory()
        
        if not inventory:
            print("No inventory data to export.")
            return False
        
        export_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "items": []
        }
        
        for item_id, quantity in inventory.items():
            item_id = int(item_id)
            details = self.get_item_details(item_id)
            market_price = self.get_market_price(item_id)
            
            export_data["items"].append({
                "item_id": item_id,
                "name": details.get("name", f"Item {item_id}") if details else f"Item {item_id}",
                "type": details.get("type", "Unknown") if details else "Unknown",
                "quantity": quantity,
                "market_price": market_price or 0,
                "total_value": (quantity * market_price) if market_price else 0
            })
        
        try:
            with open(filename, "w") as f:
                json.dump(export_data, f, indent=2)
            print(f"Inventory exported successfully to {filename}")
            return True
        except IOError as e:
            print(f"Failed to export inventory: {e}")
            return False


def main():
    """Main function to demonstrate inventory manager usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python inventory.py <API_KEY> [sort_by] [--reverse]")
        print("\nSort options: name, quantity, price, total_value, type")
        print("\nExample: python inventory.py YOUR_API_KEY quantity --reverse")
        return
    
    api_key = sys.argv[1]
    sort_by = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "name"
    reverse = "--reverse" in sys.argv
    
    manager = InventoryManager(api_key)
    manager.display_inventory(sort_by=sort_by, reverse=reverse)
    
    # Optionally export to JSON
    # manager.export_inventory_json()


if __name__ == "__main__":
    main()
