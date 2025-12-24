import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from groq import Groq
import requests

# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def get_user_info(user_id: str, api_key: str) -> Dict[str, Any]:
    """Fetch user information from Torn API"""
    try:
        url = f"https://api.torn.com/user/{user_id}?selections=&key={api_key}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user info: {e}")
        return {}

def get_inventory(user_id: str, api_key: str) -> Dict[str, Any]:
    """Fetch user inventory from Torn API"""
    try:
        url = f"https://api.torn.com/user/{user_id}?selections=inventory&key={api_key}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("inventory", {})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching inventory: {e}")
        return {}

def build_user_context(user_id: str, api_key: str) -> str:
    """Build comprehensive user context including user info and inventory"""
    user_info = get_user_info(user_id, api_key)
    inventory = get_inventory(user_id, api_key)
    
    context = f"""You are an AI advisor for the Torn game. Here is the user's current information:

User ID: {user_info.get('user_id', 'Unknown')}
Name: {user_info.get('name', 'Unknown')}
Level: {user_info.get('level', 'Unknown')}
Experience: {user_info.get('experience', 'Unknown')}
Status: {user_info.get('status', 'Unknown')}
Job: {user_info.get('job', 'Unknown')}
Faction: {user_info.get('faction', 'Unknown')}
Money: ${user_info.get('money', 0):,}
Bank: ${user_info.get('bank', 0):,}
Last Action: {user_info.get('last_action', 'Unknown')}

INVENTORY:
"""
    
    if inventory:
        inventory_items = []
        for item_id, item_data in inventory.items():
            if isinstance(item_data, dict):
                item_name = item_data.get('name', 'Unknown Item')
                quantity = item_data.get('quantity', 0)
                inventory_items.append(f"  - {item_name}: {quantity}")
            else:
                # Handle case where item_data might be just the quantity
                inventory_items.append(f"  - Item ID {item_id}: {item_data}")
        
        if inventory_items:
            context += "\n".join(inventory_items)
        else:
            context += "  (Empty inventory)"
    else:
        context += "  (Empty inventory or unable to retrieve)"
    
    context += """

Use this information to provide personalized advice about their character status, inventory management, and game strategy."""
    
    return context

def chat_with_advisor(user_id: str, api_key: str, user_message: str, chat_history: Optional[list] = None) -> str:
    """Send a message to the AI advisor and get a response"""
    if chat_history is None:
        chat_history = []
    
    # Build user context with inventory data
    system_context = build_user_context(user_id, api_key)
    
    # Add user message to history
    chat_history.append({
        "role": "user",
        "content": user_message
    })
    
    # Call Groq API
    try:
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {
                    "role": "system",
                    "content": system_context
                }
            ] + chat_history,
            temperature=0.7,
            max_tokens=1024,
        )
        
        assistant_message = response.choices[0].message.content
        chat_history.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        return assistant_message
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return "Sorry, I encountered an error while processing your request."

def format_inventory_summary(inventory: Dict[str, Any]) -> str:
    """Format inventory data into a readable summary"""
    if not inventory:
        return "Inventory is empty"
    
    summary_lines = []
    total_items = 0
    
    for item_id, item_data in inventory.items():
        if isinstance(item_data, dict):
            item_name = item_data.get('name', 'Unknown')
            quantity = item_data.get('quantity', 0)
        else:
            item_name = f"Item {item_id}"
            quantity = item_data
        
        summary_lines.append(f"{item_name}: {quantity}")
        total_items += quantity
    
    summary = "\n".join(summary_lines)
    return f"{summary}\n\nTotal items: {total_items}"

def main():
    """Main function for testing"""
    user_id = "123456"  # Replace with actual user ID
    api_key = os.environ.get("TORN_API_KEY")
    
    if not api_key:
        print("Error: TORN_API_KEY environment variable not set")
        return
    
    # Example: Get inventory
    print("Fetching inventory...")
    inventory = get_inventory(user_id, api_key)
    print("Inventory Summary:")
    print(format_inventory_summary(inventory))
    
    # Example: Chat with advisor
    print("\n" + "="*50)
    print("Chat with AI Advisor")
    print("="*50)
    
    chat_history = []
    
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
        
        if not user_input:
            continue
        
        response = chat_with_advisor(user_id, api_key, user_input, chat_history)
        print(f"\nAdvisor: {response}")

if __name__ == "__main__":
    main()
