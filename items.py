"""
Item ID Lookup for Torn City items.
Maps item names to their IDs for Market API calls.
"""

# Popular items dictionary (manual mapping for speed)
# Format: "lowercase_name": item_id
POPULAR_ITEMS = {
    # Drugs
    "xanax": 206,
    "ecstasy": 197,
    "vicodin": 198,
    "shrooms": 199,
    "speed": 200,
    "pcp": 201,
    "lsd": 202,
    "ketamine": 203,
    "cannabis": 204,
    "opium": 205,
    
    # Medical
    "first aid kit": 180,
    "small first aid kit": 68,
    "morphine": 181,
    "blood bag": 182,
    
    # Boosters
    "energy drink": 159,
    "can of munster": 160,
    "can of red cow": 161,
    "lollipop": 162,
    "bag of candy": 163,
    "box of chocolate": 164,
    "e-dvd": 169,
    "edvd": 169,
    "feathery hotel coupon": 170,
    "fhc": 170,
    
    # Plushies (Travel items)
    "lion plushie": 261,
    "monkey plushie": 266,
    "chamois plushie": 268,
    "sheep plushie": 269,
    "panda plushie": 270,
    "jaguar plushie": 271,
    "wolverine plushie": 272,
    "nessie plushie": 273,
    "red fox plushie": 274,
    "kitten plushie": 215,
    "camel plushie": 258,
    "stingray plushie": 259,
    "teddy bear plushie": 267,
    
    # Flowers
    "african violet": 260,
    "banana orchid": 264,
    "cherry blossom": 263,
    "dahlia": 265,
    "edelweiss": 262,
    "heather": 277,
    "ceibo flower": 276,
    "orchid": 278,
    "peony": 279,
    "crocus": 282,
    "tribulus omanense": 271,
    
    # Other popular
    "box of grenades": 103,
    "claymore mine": 224,
}


def get_item_id(name: str) -> int | None:
    """
    Get item ID from item name.
    
    Args:
        name: Item name (case-insensitive)
    
    Returns:
        int: Item ID if found, None otherwise
    """
    name_lower = name.lower().strip()
    return POPULAR_ITEMS.get(name_lower)


def get_item_name(item_id: int) -> str | None:
    """
    Get item name from item ID (reverse lookup).
    
    Args:
        item_id: Torn item ID
    
    Returns:
        str: Item name if found, None otherwise
    """
    for name, id_ in POPULAR_ITEMS.items():
        if id_ == item_id:
            return name.title()
    return None


# Medical item IDs for /stock command filtering
MEDICAL_ITEM_IDS = [68, 180, 181, 182, 183, 184, 185, 186, 187, 188]

# Booster item IDs for /stock command filtering
BOOSTER_ITEM_IDS = [159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170]
