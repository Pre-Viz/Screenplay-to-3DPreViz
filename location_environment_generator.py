#!/usr/bin/env python3
"""
Step 2: Location Environment Asset Generator
Analyzes the location/setting and suggests appropriate background/environment objects

This script:
1. Reads the location from Step 1 JSON output
2. Uses Ollama to suggest environment objects (trees, bushes, rocks, furniture, etc.)
3. Validates against asset library
4. Outputs JSON with environment objects needed
5. Creates newLocationAssetsNeeded.txt for missing assets
"""

import subprocess
import json
import os
from datetime import datetime

class LocationEnvironmentGenerator:
    def __init__(self, model="llama3", readme_path="README.md"):
        self.model = model
        self.readme_path = readme_path
        self.asset_info = self._load_asset_info_from_readme()
    
    def _load_asset_info_from_readme(self):
        """Load asset pack information from README.md"""
        
        asset_info = {
            "packs": {},
            "scaling": {}
        }
        
        if not os.path.exists(self.readme_path):
            print(f"⚠️ README not found at {self.readme_path}")
            return asset_info
        
        try:
            with open(self.readme_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Parse asset folder structure
            in_asset_section = False
            current_pack = None
            
            for line in lines:
                if "Complete Asset Folder Structure" in line or "Asset Folder Structure" in line:
                    in_asset_section = True
                    continue
                
                if in_asset_section and line.startswith("##") and "Asset" not in line:
                    in_asset_section = False
                
                if in_asset_section:
                    # Pack directory lines like "├── Ultimate House Interior Pack-glb" or "└── outdoors"
                    if ("├──" in line or "└──" in line) and not line.strip().endswith('.glb'):
                        # Handle both ├── and └── patterns
                        if "├──" in line:
                            pack_match = line.split('├──')[-1].split('│')[-1].strip()
                        else:
                            pack_match = line.split('└──')[-1].split('│')[-1].strip()
                        # Filter out empty strings, texture folders, and special characters
                        if pack_match and pack_match not in ['Textures', '']:
                            # This looks like a pack/folder name
                            current_pack = pack_match
                            if current_pack not in asset_info["packs"]:
                                asset_info["packs"][current_pack] = []
                    
                    # Asset files like "│   ├── Bathtub.glb" or "    └── Statue.glb"
                    elif current_pack and ".glb" in line and ("├──" in line or "└──" in line):
                        if "├──" in line:
                            asset_name = line.split('├──')[-1].strip()
                        else:
                            asset_name = line.split('└──')[-1].strip()
                        if asset_name.endswith('.glb'):
                            asset_info["packs"][current_pack].append(asset_name)
            
            print(f"✅ Loaded {len(asset_info['packs'])} asset packs from README")
            
        except Exception as e:
            print(f"⚠️ Error reading README: {e}")
        
        return asset_info
    
    def generate_environment_assets(self, step1_json_file):
        """
        Generate environment assets based on Step 1 location analysis
        
        Args:
            step1_json_file: JSON file from Step 1 (contains location, environment_type, etc.)
        
        Returns:
            dict: Environment assets needed
        """
        
        print("🌍 STEP 2: Location Environment Asset Generator")
        print("=" * 60)
        
        # Load Step 1 results
        try:
            with open(step1_json_file, 'r') as f:
                step1_data = json.load(f)
        except Exception as e:
            print(f"❌ Error reading Step 1 JSON: {e}")
            return None
        
        location = step1_data.get('location', 'Unknown')
        env_type = step1_data.get('environment_type', 'Unknown')
        
        print(f"📍 Location: {location}")
        print(f"🎬 Environment Type: {env_type}")
        
        # Create prompt for Ollama
        prompt = self._create_environment_prompt(location, env_type)
        
        # Call Ollama
        print("\n🤖 Analyzing environment requirements with Ollama...")
        result = self._call_ollama(prompt)
        
        if result:
            print("✅ Environment analysis complete!")
            return result
        else:
            print("❌ Environment analysis failed")
            return None
    
    def _create_environment_prompt(self, location, env_type):
        """Create prompt for Ollama to suggest environment objects"""
        
        # Build DETAILED available assets list from README
        available_packs_text = "AVAILABLE ENVIRONMENT ASSET PACKS (USE ONLY THESE EXACT FILES):\n\n"
        
        # Determine which packs to show based on location type
        location_lower = location.lower()
        env_lower = env_type.lower()
        
        # Smart pack selection based on environment
        if any(word in location_lower or word in env_lower for word in ['forest', 'nature', 'park', 'outdoor', 'wilderness', 'woods']):
            # Nature-heavy environment - show ALL nature assets
            relevant_packs = [
                "Stylized Nature MegaKit.undefined-glb",
                "Ultimate Stylized Nature Pack-glb",
                "Survival Pack-glb"
            ]
        elif any(word in location_lower or word in env_lower for word in ['bedroom', 'office', 'kitchen', 'room', 'interior', 'house']):
            # Indoor environment - FURNITURE PACK FIRST for office essentials!
            relevant_packs = [
                "Furniture Pack-glb",  # Has Desk, Office Chair, Bookcase - SHOW FIRST!
                "Ultimate House Interior Pack-glb"
            ]
        elif any(word in location_lower or word in env_lower for word in ['medieval', 'castle', 'village', 'fantasy']):
            # Medieval environment
            relevant_packs = [
                "Medieval Village Pack-glb",
                "Stylized Nature MegaKit.undefined-glb"
            ]
        else:
            # Default - show all
            relevant_packs = [
                "Stylized Nature MegaKit.undefined-glb",
                "Ultimate Stylized Nature Pack-glb",
                "Medieval Village Pack-glb",
                "Ultimate House Interior Pack-glb",
                "Furniture Pack-glb",
                "Survival Pack-glb"
            ]
        
        for pack_name in relevant_packs:
            assets = self.asset_info["packs"].get(pack_name, [])
            if assets:
                available_packs_text += f"\n{pack_name} ({len(assets)} files available):\n"
                # Show MANY assets for nature and interior packs
                if 'Nature' in pack_name:
                    max_show = 60  # Show lots of nature variety
                elif 'Interior' in pack_name or 'Furniture' in pack_name:
                    max_show = 60  # Show lots of furniture options
                else:
                    max_show = 30
                
                for asset in assets[:max_show]:
                    available_packs_text += f"  - {pack_name}/{asset}\n"
                if len(assets) > max_show:
                    available_packs_text += f"  ... and {len(assets) - max_show} more files available\n"
        
        prompt = f"""You are an EXPERT environment designer. Your task is to create REALISTIC, DETAILED environments for ANY location type.

LOCATION: {location}
ENVIRONMENT TYPE: {env_type}

CRITICAL INSTRUCTION: Analyze the location type carefully and select APPROPRIATE assets that make sense for THIS SPECIFIC environment.

═══════════════════════════════════════════════════════════
ENVIRONMENT DESIGN GUIDELINES BY LOCATION TYPE:
═══════════════════════════════════════════════════════════

🌲 FORESTS/NATURE (forest, woods, park, wilderness, jungle):
   Essential: MANY trees (8-20x multiple varieties), bushes (10-30x), ground plants (30-60x)
   Ground Cover: Grass, Clover, Ferns, Flowers, Tall Grass, Mushrooms
   Large Objects: Pine Trees, Birch, Oak, Twisted Trees, Dead Trees, Large Rocks
   Details: Medium/Small Rocks, Pebbles, Wood Logs, Stumps, Mushroom Circles
   Quantity: 150-300 objects for dense, realistic nature
   
🏢 OFFICE (office, workplace, study, workspace):
   Essential: DESK (Furniture Pack), Office Chair, Bookcase
   Furniture: Extra chairs (2-3x), Sofa/Couch (1x), Side tables
   Storage: Bookcase with Books, Drawers, Shelves, Closet
   Lighting: Ceiling lights (2-3x), Desk lamp, Floor lamp
   Details: Houseplants (2-4x), Rug, Trashcan, Curtains
   Quantity: 12-20 objects for professional office
   
🛏️ BEDROOM (bedroom, sleeping area):
   Essential: BED (King/Queen/Single), Night Stand (1-2x)
   Furniture: Dresser/Drawer, Closet, Chair, Desk (optional)
   Lighting: Ceiling light, Table lamp, Floor lamp
   Decor: Rug, Curtains, Plants (1-2x), Mirror
   Details: Small items on nightstand
   Quantity: 10-18 objects for cozy bedroom
   
🍳 KITCHEN (kitchen, cooking area, dining room):
   Essential: Table, Chairs (4-6x), Counter/Island
   Appliances: Stove, Fridge (use closet as substitute), Sink
   Storage: Cabinets, Shelves, Drawers
   Lighting: Ceiling lights (2-3x), Pendant lights
   Details: Plants (1-2x), Rug, Trashcan
   Quantity: 15-25 objects for functional kitchen
   
🛁 BATHROOM (bathroom, washroom):
   Essential: Toilet, Sink, Bathtub or Shower
   Storage: Cabinets, Shelves, Drawers
   Lighting: Ceiling light, Mirror light
   Details: Toilet paper holder, Plants (1x), Rug, Trashcan
   Quantity: 8-15 objects for complete bathroom
   
🏠 LIVING ROOM (living room, lounge, family room):
   Essential: Large Couch/Sofa, Chairs (2-4x), Coffee Table
   Furniture: TV stand (use table), Bookcase, Side tables
   Lighting: Ceiling lights, Floor lamps (2x), Table lamps
   Decor: Rug, Plants (3-5x), Curtains
   Quantity: 15-25 objects for comfortable living room
   
🏙️ STREET/URBAN (street, city, downtown, urban area):
   Essential: Buildings (3-8x), Road/Path elements
   Urban: Street lights, Benches, Trash bins
   Vehicles: Cars (2-5x) if available
   Nature: Trees (3-6x), Bushes (5-10x) for landscaping
   Details: Rocks, small structures
   Quantity: 20-40 objects for realistic street
   
🏖️ BEACH/COAST (beach, shore, coast, seaside):
   Essential: Sand (use grass as ground), Rocks (10-20x), Pebbles (20-30x)
   Nature: Palm trees or coastal trees (5-10x), Beach grass, Bushes
   Details: Driftwood (use logs), Large boulders, Shells (use small rocks)
   Optional: Beach chair (use stool), Umbrella substitute
   Quantity: 50-100 objects for natural beach
   
🏰 MEDIEVAL/CASTLE (castle, medieval, village, fortress):
   Essential: Medieval buildings (3-8x), Walls, Towers
   Structures: Gates, Paths, Fences
   Nature: Trees (5-10x), Bushes (10-15x), Grass
   Details: Barrels (use crates), Carts, Rocks
   Quantity: 30-60 objects for medieval setting
   
🌾 FARM/RURAL (farm, barn, countryside, rural):
   Essential: Barn/Building structures, Fences
   Nature: Trees (8-15x), Bushes, Tall grass (30-50x), Flowers
   Details: Hay bales (use crates), Tools, Rocks, Wood logs
   Animals: Use available animal models if present
   Quantity: 50-120 objects for farm environment
   
🏪 STORE/SHOP (store, shop, market, retail):
   Essential: Shelves (4-8x), Counter/Desk, Chairs (2-4x)
   Display: Tables, Stands, Storage units
   Lighting: Ceiling lights (3-5x)
   Details: Plants (1-2x), Trashcan, Rug, Signs (use pictures)
   Quantity: 15-30 objects for functional store
   
🍽️ RESTAURANT/CAFE (restaurant, cafe, diner, eatery):
   Essential: Tables (4-8x), Chairs (12-24x)
   Furniture: Counter/Bar, Stools, Shelves
   Lighting: Ceiling lights (4-6x), Table lamps
   Decor: Plants (3-6x), Rugs, Curtains
   Details: Trashcans, Small tables
   Quantity: 25-50 objects for restaurant atmosphere
   
🎪 SPECIAL ENVIRONMENTS:
   - Spaceship/Sci-fi: Use furniture + lights creatively, minimal plants
   - Cave: Rocks (30-50x), boulders, mushrooms, dark atmosphere
   - Garden: MANY plants (40-80x), flowers, bushes, trees, rocks
   - Laboratory: Desks (3-5x), chairs, shelves, minimal decor
   - Warehouse: Crates (use drawers/closets), minimal furniture
   
═══════════════════════════════════════════════════════════
KEY PRINCIPLES (APPLY TO ALL ENVIRONMENTS):
═══════════════════════════════════════════════════════════
✓ VARIETY: Use 5-15 DIFFERENT asset types, not just one
✓ REALISTIC QUANTITIES: Match real-world density
✓ FUNCTIONAL: Include what people actually need/use
✓ LIVED-IN: Add details that show people use this space
✓ APPROPRIATE: Match assets to location (no trees in bathroom!)
✓ BALANCED: Mix large/small, functional/decorative objects

{available_packs_text}

OUTPUT FORMAT (JSON):
{{
  "location": "{location}",
  "environment_type": "{env_type}",
  "ground_cover": [
    {{"name": "OBJECT_NAME", "suggested_glb": "Pack-glb/Object.glb", "count": 10, "scatter": true}}
  ],
  "large_objects": [
    {{"name": "OBJECT_NAME", "suggested_glb": "Pack-glb/Object.glb", "count": 3, "scatter": true}}
  ],
  "structural_elements": [
    {{"name": "OBJECT_NAME", "suggested_glb": "Pack-glb/Object.glb", "count": 1, "scatter": false}}
  ],
  "ambient_objects": [
    {{"name": "OBJECT_NAME", "suggested_glb": "Pack-glb/Object.glb", "count": 5, "scatter": true}}
  ]
}}

═══════════════════════════════════════════════════════════
CRITICAL RULES - MUST FOLLOW EXACTLY:
═══════════════════════════════════════════════════════════
1. ⚠️  ONLY use EXACT file paths from the asset list above - DO NOT make up file names
2. ⚠️  COPY-PASTE paths EXACTLY - including dots, slashes, dashes, parentheses
3. ⚠️  Pay attention to: "." (dot) vs "/" (slash) vs "-" (dash) vs "(" (parenthesis)
4. ⚠️  Example CORRECT: "Stylized Nature MegaKit.undefined-glb/Bush.glb" (note the DOT)
5. ⚠️  If unsure of path, search the asset list above - it's all there
6. ⚠️  MATCH ENVIRONMENT TYPE: Don't put trees in bathrooms or beds in forests!
7. ⚠️  USE APPROPRIATE QUANTITIES: Match the guidelines for each location type
8. Set scatter=true for random placement (trees, rocks, plants, small decor)
9. Set scatter=false for specific placement (furniture, buildings, appliances)
10. Categories explained:
    • ground_cover: grass, flowers, small plants, rugs (high count, scattered)
    • large_objects: trees, furniture, vehicles, buildings (medium count)
    • structural_elements: walls, doors, major structures (low count, placed)
    • ambient_objects: bushes, lamps, decorative items (medium count, scattered)

═══════════════════════════════════════════════════════════
EXAMPLE OUTPUTS (showing correct variety and quantities):
═══════════════════════════════════════════════════════════

Example 1 - DENSE FOREST:
{{
  "ground_cover": [
    {{"name": "Grass", "suggested_glb": "Stylized Nature MegaKit.undefined-glb/Grass.glb", "count": 50, "scatter": true}},
    {{"name": "Clover", "suggested_glb": "Stylized Nature MegaKit.undefined-glb/Clover.glb", "count": 30, "scatter": true}},
    {{"name": "Fern", "suggested_glb": "Ultimate Stylized Nature Pack-glb/Fern.glb", "count": 25, "scatter": true}},
    {{"name": "Flowers Group", "suggested_glb": "Stylized Nature MegaKit.undefined-glb/Flowers Group.glb", "count": 20, "scatter": true}}
  ],
  "large_objects": [
    {{"name": "Pine Tree", "suggested_glb": "Stylized Nature MegaKit.undefined-glb/Tree Pine.glb", "count": 12, "scatter": true}},
    {{"name": "Birch Tree", "suggested_glb": "Ultimate Stylized Nature Pack-glb/Tree Birch.glb", "count": 8, "scatter": true}},
    {{"name": "Large Rock", "suggested_glb": "Stylized Nature MegaKit.undefined-glb/Rock Large.glb", "count": 6, "scatter": true}}
  ],
  "structural_elements": [],
  "ambient_objects": [
    {{"name": "Bush", "suggested_glb": "Stylized Nature MegaKit.undefined-glb/Bush.glb", "count": 20, "scatter": true}},
    {{"name": "Mushrooms", "suggested_glb": "Ultimate Stylized Nature Pack-glb/Mushrooms.glb", "count": 15, "scatter": true}}
  ]
}}

Example 2 - PROFESSIONAL OFFICE:
{{
  "ground_cover": [
    {{"name": "Rug", "suggested_glb": "Ultimate House Interior Pack-glb/Round Rug.glb", "count": 1, "scatter": false}}
  ],
  "large_objects": [
    {{"name": "Desk", "suggested_glb": "Furniture Pack-glb/Desk.glb", "count": 1, "scatter": false}},
    {{"name": "Office Chair", "suggested_glb": "Furniture Pack-glb/Office Chair.glb", "count": 1, "scatter": false}},
    {{"name": "Bookcase", "suggested_glb": "Furniture Pack-glb/Bookcase with Books.glb", "count": 1, "scatter": false}},
    {{"name": "Sofa", "suggested_glb": "Furniture Pack-glb/Sofa.glb", "count": 1, "scatter": false}}
  ],
  "structural_elements": [
    {{"name": "Door", "suggested_glb": "Ultimate House Interior Pack-glb/Door.glb", "count": 1, "scatter": false}}
  ],
  "ambient_objects": [
    {{"name": "Houseplant", "suggested_glb": "Ultimate House Interior Pack-glb/Houseplant-IBLX2Jz90O.glb", "count": 3, "scatter": true}},
    {{"name": "Ceiling Light", "suggested_glb": "Ultimate House Interior Pack-glb/Ceiling Light.glb", "count": 2, "scatter": false}}
  ]
}}

Example 3 - COZY BEDROOM:
{{
  "ground_cover": [
    {{"name": "Rug", "suggested_glb": "Ultimate House Interior Pack-glb/Round Rug.glb", "count": 1, "scatter": false}}
  ],
  "large_objects": [
    {{"name": "Bed King", "suggested_glb": "Ultimate House Interior Pack-glb/Bed King.glb", "count": 1, "scatter": false}},
    {{"name": "Night Stand", "suggested_glb": "Furniture Pack-glb/Night Stand.glb", "count": 2, "scatter": false}},
    {{"name": "Drawer", "suggested_glb": "Ultimate House Interior Pack-glb/Drawer-G1H0wnCHQf.glb", "count": 1, "scatter": false}},
    {{"name": "Closet", "suggested_glb": "Furniture Pack-glb/Closet.glb", "count": 1, "scatter": false}}
  ],
  "structural_elements": [
    {{"name": "Door", "suggested_glb": "Furniture Pack-glb/Door.glb", "count": 1, "scatter": false}}
  ],
  "ambient_objects": [
    {{"name": "Table Lamp", "suggested_glb": "Ultimate House Interior Pack-glb/Table Lamp.glb", "count": 2, "scatter": false}},
    {{"name": "Houseplant", "suggested_glb": "Ultimate House Interior Pack-glb/Cactus.glb", "count": 1, "scatter": true}},
    {{"name": "Curtains", "suggested_glb": "Ultimate House Interior Pack-glb/Curtains Double.glb", "count": 2, "scatter": false}}
  ]
}}

═══════════════════════════════════════════════════════════
NOW GENERATE THE ENVIRONMENT FOR: {location} ({env_type})
═══════════════════════════════════════════════════════════

Analyze the location type above, match it to the appropriate guidelines, and create a complete environment.
Remember: Use ONLY assets from the provided list, match appropriate quantities, and make it realistic!

Provide ONLY the JSON output, no other text."""

        return prompt
    
    def _call_ollama(self, prompt):
        """Call Ollama API to analyze environment needs"""
        
        try:
            cmd = ["ollama", "run", self.model]
            
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                
                # Extract JSON from output
                json_start = output.find('{')
                json_end = output.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = output[json_start:json_end]
                    parsed_result = json.loads(json_str)
                    return parsed_result
                else:
                    print("⚠️ Could not find JSON in response")
                    return None
            else:
                print(f"❌ Ollama error: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print("❌ Ollama request timed out (>60s)")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON: {e}")
            return None
        except Exception as e:
            print(f"❌ Error calling Ollama: {e}")
            return None
    
    def validate_environment_assets(self, environment_data):
        """Validate environment assets against library"""
        
        validation = {
            "available": [],
            "missing": []
        }
        
        if not environment_data:
            return validation
        
        # Collect all requested GLBs from all categories
        all_requests = []
        
        categories = ['ground_cover', 'large_objects', 'structural_elements', 'ambient_objects']
        
        for category in categories:
            items = environment_data.get(category, [])
            for item in items:
                glb = item.get('suggested_glb', '')
                if glb:
                    all_requests.append({
                        'category': category,
                        'name': item.get('name'),
                        'glb': glb,
                        'count': item.get('count', 1),
                        'scatter': item.get('scatter', True)
                    })
        
        # Validate each GLB
        for request in all_requests:
            glb_path = request['glb']
            exists = self._check_glb_exists(glb_path)
            
            if exists:
                validation['available'].append(request)
            else:
                validation['missing'].append(request)
        
        return validation
    
    def _check_glb_exists(self, glb_path):
        """Check if a GLB file exists in the asset packs"""
        
        if '/' in glb_path:
            pack_name, filename = glb_path.rsplit('/', 1)
        else:
            return False
        
        pack_assets = self.asset_info['packs'].get(pack_name, [])
        return filename in pack_assets
    
    def display_environment_results(self, environment_data, validation=None):
        """Display environment assets in a nice format"""
        
        if not environment_data:
            return
        
        print("\n" + "=" * 60)
        print("🌍 ENVIRONMENT ASSETS NEEDED")
        print("=" * 60)
        
        def get_status(glb_path):
            if not validation:
                return ""
            for item in validation['available']:
                if item.get('glb') == glb_path:
                    return "✅"
            for item in validation['missing']:
                if item.get('glb') == glb_path:
                    return "❌"
            return "❓"
        
        categories = [
            ('ground_cover', '🌱 GROUND COVER'),
            ('large_objects', '🌳 LARGE OBJECTS'),
            ('structural_elements', '🏗️ STRUCTURAL ELEMENTS'),
            ('ambient_objects', '🎨 AMBIENT OBJECTS')
        ]
        
        total_objects = 0
        
        for key, title in categories:
            items = environment_data.get(key, [])
            if items:
                print(f"\n{title}:")
                for i, item in enumerate(items, 1):
                    count = item.get('count', 1)
                    scatter = item.get('scatter', True)
                    scatter_text = "(scattered)" if scatter else "(placed)"
                    status = get_status(item.get('suggested_glb', ''))
                    
                    print(f"   {i}. {status} {item.get('name', 'Unknown')} x{count} {scatter_text}")
                    print(f"      GLB: {item.get('suggested_glb', 'Not found')}")
                    
                    total_objects += count
        
        print(f"\n✅ Total environment objects: {total_objects}")
        
        # Validation summary
        if validation:
            print("\n" + "=" * 60)
            print("🔍 ASSET VALIDATION:")
            print("=" * 60)
            print(f"✅ Available in library: {len(validation['available'])}")
            print(f"❌ Missing from library: {len(validation['missing'])}")
            
            if validation['missing']:
                print("\n⚠️  WARNING: Some environment assets are not in the library!")
                print("   A detailed report will be saved to 'newLocationAssetsNeeded.txt'")
    
    def save_environment_results(self, environment_data, output_file="environment_assets.json"):
        """Save environment assets to JSON file"""
        
        if not environment_data:
            return False
        
        try:
            with open(output_file, 'w') as f:
                json.dump(environment_data, f, indent=2)
            print(f"\n💾 Environment assets saved to: {output_file}")
            return True
        except Exception as e:
            print(f"❌ Failed to save results: {e}")
            return False
    
    def save_missing_location_assets_report(self, validation, output_file="newLocationAssetsNeeded.txt"):
        """Append missing location assets report to file (newer entries at top)"""
        
        if not validation or not validation['missing']:
            return False
        
        try:
            # Read existing content if file exists
            existing_content = ""
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    existing_content = f.read()
            
            # Create new entry
            new_entry = []
            new_entry.append("=" * 60 + "\n")
            new_entry.append("NEW LOCATION/ENVIRONMENT ASSETS NEEDED - LATEST ENTRY\n")
            new_entry.append("=" * 60 + "\n\n")
            new_entry.append(f"Total missing assets: {len(validation['missing'])}\n")
            new_entry.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Group by category
            by_category = {
                'ground_cover': [],
                'large_objects': [],
                'structural_elements': [],
                'ambient_objects': []
            }
            
            for item in validation['missing']:
                category = item.get('category', 'ambient_objects')
                if category in by_category:
                    by_category[category].append(item)
            
            # Write each category
            category_titles = {
                'ground_cover': 'GROUND COVER (Grass, Flowers, Small Plants)',
                'large_objects': 'LARGE OBJECTS (Trees, Buildings, Large Rocks)',
                'structural_elements': 'STRUCTURAL ELEMENTS (Walls, Paths, Major Structures)',
                'ambient_objects': 'AMBIENT OBJECTS (Bushes, Furniture, Decorative Items)'
            }
            
            for category, title in category_titles.items():
                if by_category[category]:
                    new_entry.append("\n" + "=" * 60 + "\n")
                    new_entry.append(f"{title}\n")
                    new_entry.append("=" * 60 + "\n")
                    for item in by_category[category]:
                        count = item.get('count', 1)
                        scatter = item.get('scatter', True)
                        scatter_text = " (scattered placement)" if scatter else " (specific placement)"
                        
                        new_entry.append(f"\n• {item['name']} (needed: {count}x){scatter_text}\n")
                        new_entry.append(f"  Requested path: {item['glb']}\n")
                        new_entry.append(f"  Action needed: Create or find environment asset\n")
            
            # Summary
            new_entry.append("\n" + "=" * 60 + "\n")
            new_entry.append("RECOMMENDATIONS\n")
            new_entry.append("=" * 60 + "\n")
            new_entry.append("1. Search for similar environment assets in existing packs\n")
            new_entry.append("2. Download/purchase nature or environment asset packs\n")
            new_entry.append("3. Use procedural generation for ground cover\n")
            new_entry.append("4. Use placeholder objects temporarily\n")
            new_entry.append("\n")
            
            # Add separator
            new_entry.append("\n" + "#" * 60 + "\n")
            new_entry.append("# PREVIOUS ENTRIES BELOW\n")
            new_entry.append("#" * 60 + "\n\n")
            
            # Write new entry at top, then existing content
            with open(output_file, 'w') as f:
                f.write("".join(new_entry))
                if existing_content:
                    if "PREVIOUS ENTRIES BELOW" in existing_content:
                        parts = existing_content.split("# PREVIOUS ENTRIES BELOW\n")
                        if len(parts) > 1:
                            f.write(parts[1].lstrip("#").lstrip("=").lstrip("\n"))
                    else:
                        f.write(existing_content)
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving missing location assets report: {e}")
            return False

def main():
    """Example usage - generate environment assets from Step 1 output"""
    
    import sys
    
    # Check if Step 1 JSON file is provided
    if len(sys.argv) > 1:
        step1_file = sys.argv[1]
    else:
        # Use default if exists
        step1_file = "parsed_screenplay_glbs.json"
        if not os.path.exists(step1_file):
            print("❌ No Step 1 JSON file found")
            print("Usage: python location_environment_generator.py <step1_json_file>")
            print("Example: python location_environment_generator.py parsed_screenplay_glbs.json")
            return
    
    print("🌍 LOCATION ENVIRONMENT GENERATOR - STEP 2")
    print("=" * 60)
    print(f"📂 Reading Step 1 results from: {step1_file}\n")
    
    generator = LocationEnvironmentGenerator()
    
    # Generate environment assets
    environment_data = generator.generate_environment_assets(step1_file)
    
    if environment_data:
        # Validate assets
        validation = generator.validate_environment_assets(environment_data)
        
        # Display results
        generator.display_environment_results(environment_data, validation)
        
        # Save results
        generator.save_environment_results(environment_data, "environment_assets.json")
        
        # Save missing assets report if needed
        if validation['missing']:
            generator.save_missing_location_assets_report(validation)
            print("\n📝 Missing location assets report saved: newLocationAssetsNeeded.txt")
        
        print("\n✅ Step 2 Complete!")
        print("💡 Next step: Combine Step 1 (characters/props) + Step 2 (environment) for scene assembly")
    else:
        print("\n❌ Failed to generate environment assets")

if __name__ == "__main__":
    main()
