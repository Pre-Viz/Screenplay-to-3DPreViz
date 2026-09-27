#!/usr/bin/env python3
"""
Screenplay Parser - Step 1
Reads a screenplay and identifies all GLB files needed for the scene.

This script:
1. Takes a screenplay text as input
2. Uses Ollama (llama3) to analyze the screenplay
3. Outputs a list of required GLB files for:
   - Location/Environment
   - Characters
   - Props/Objects
"""

import subprocess
import json
import os

class ScreenplayParser:
    def __init__(self, model="llama3", readme_path="README.md"):
        self.model = model
        self.assets_base = "assets"
        self.readme_path = readme_path
        self.asset_info = self._load_asset_info_from_readme()
    
    def parse_screenplay(self, screenplay_text):
        """
        Parse screenplay and extract required GLB files
        
        Args:
            screenplay_text: The screenplay text to analyze
            
        Returns:
            dict: Dictionary containing lists of required GLB files
        """
        
        print("🎬 Screenplay Parser - Step 1")
        print("=" * 50)
        print(f"📄 Analyzing screenplay ({len(screenplay_text)} characters)...")
        
        # Create prompt for Ollama
        prompt = self._create_analysis_prompt(screenplay_text)
        
        # Call Ollama
        print("\n🤖 Calling Ollama to analyze screenplay...")
        result = self._call_ollama(prompt)
        
        if result:
            print("\n✅ Analysis complete!")
            return result
        else:
            print("\n❌ Analysis failed")
            return None
    
    def _load_asset_info_from_readme(self):
        """Load asset pack information from README.md"""
        
        asset_info = {
            "packs": {},
            "scaling": {}
        }
        
        if not os.path.exists(self.readme_path):
            print(f"⚠️ README not found at {self.readme_path}, using defaults")
            return asset_info
        
        try:
            with open(self.readme_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Parse asset folder structure section
            in_asset_section = False
            current_pack = None
            
            for line in lines:
                # Look for asset folder structure
                if "Complete Asset Folder Structure" in line or "Asset Folder Structure" in line:
                    in_asset_section = True
                    continue
                
                # Stop at next major section
                if in_asset_section and line.startswith("##") and "Asset" not in line:
                    in_asset_section = False
                
                # Parse pack names and files
                if in_asset_section:
                    # Pack directory lines like "├── Ultimate House Interior Pack-glb" or "└── outdoors"
                    # Check if this is a directory line (ends with folder name, not .glb)
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
                
                # Parse scaling guidelines
                if "Asset Scaling Guidelines" in line:
                    in_scaling = True
                    continue
                
                if "in_scaling" in locals() and in_scaling and "|" in line and "Pack" in line:
                    parts = [p.strip() for p in line.split('|') if p.strip()]
                    if len(parts) >= 2 and "x" in parts[1]:
                        pack_name = parts[0]
                        scale_str = parts[1]
                        try:
                            scale = float(scale_str.replace('x', '').strip())
                            asset_info["scaling"][pack_name] = scale
                        except:
                            pass
            
            print(f"✅ Loaded {len(asset_info['packs'])} asset packs from README")
            print(f"✅ Loaded {len(asset_info['scaling'])} scaling guidelines from README")
            
        except Exception as e:
            print(f"⚠️ Error reading README: {e}")
        
        return asset_info
    
    def _create_analysis_prompt(self, screenplay_text):
        """Create a detailed prompt for Ollama to analyze the screenplay"""
        
        # Build available assets list from README
        available_packs_text = "AVAILABLE ASSET PACKS:\n"
        
        for pack_name, assets in self.asset_info["packs"].items():
            if assets:
                # Show first 10 assets as examples
                sample_assets = assets[:10]
                asset_list = ", ".join([a.replace('.glb', '') for a in sample_assets])
                if len(assets) > 10:
                    asset_list += f", etc. ({len(assets)} total)"
                available_packs_text += f"- {pack_name}: {asset_list}\n"
        
        prompt = f"""You are a scene analysis assistant. Analyze this screenplay and identify all the GLB 3D assets needed.

SCREENPLAY:
{screenplay_text}

Your task is to identify and list:
1. LOCATION/ENVIRONMENT - What is the setting? (e.g., bedroom, park, office, forest)
2. CHARACTERS - Who are the people/animals in the scene?
3. PROPS/OBJECTS - What objects are mentioned or needed?

Based on the available asset packs, suggest specific GLB files:

{available_packs_text}

OUTPUT FORMAT (JSON) - BE SPECIFIC WITH FULL FILE PATHS:
{{
  "location": "description of location",
  "environment_type": "INT. BEDROOM or EXT. PARK, etc.",
  "characters": [
    {{"name": "CHARACTER_NAME", "description": "brief description", "suggested_glb": "Ultimate Modular Men Pack-glb/Beach Character.glb"}}
  ],
  "props": [
    {{"name": "PROP_NAME", "description": "brief description", "suggested_glb": "Ultimate House Interior Pack-glb/Bathtub.glb"}}
  ],
  "environment_objects": [
    {{"name": "OBJECT_NAME", "suggested_glb": "Stylized Nature MegaKit.undefined-glb/Tree.glb", "count": 3}}
  ]
}}

EXAMPLE FOR OFFICE SCENE:
If screenplay mentions: "PERSON working at desk on computer in cubicle"
Output should be:
{{
  "props": [
    {{"name": "desk", "description": "office desk with computer", "suggested_glb": "office/Desk.glb"}}
  ],
  "environment_objects": [
    {{"name": "cubicle", "suggested_glb": "office/Cubicle.glb", "count": 1}}
  ]
}}
Note: No separate "computer" prop needed - it's part of the desk!

CRITICAL RULES - READ CAREFULLY:
1. ⚠️ Use COMPLETE file paths like "Ultimate House Interior Pack-glb/Bathtub.glb"
2. ⚠️ Match character descriptions to specific character GLB files (e.g., "beach attire" = "Beach Character.glb")
3. ⚠️ For OFFICE scenes, use "office" folder for office-specific items:
   - ALWAYS include DESKS for office scenes → use "office/Desk.glb" (includes built-in computer and chair!)
   - If screenplay mentions "computer", treat it as part of the desk - don't add a separate computer prop
   - For CUBICLE WALLS → use "office/Cubicle.glb"
   - For PRINTER → use "office/Printer.glb"
   - For OFFICE PHONE → use "office/Office Phone.glb"
   - For MESSAGE BOARD → use "office/Message board.glb"
   - For standalone furniture → use "Furniture Pack-glb/..." (chairs, bookcases, sofas, etc.)
4. ⚠️ Be PRECISE with file names and avoid duplicates!
5. ⚠️ Include appropriate environment objects based on location
6. ⚠️ Be specific - use exact GLB file names from the packs listed above

Provide ONLY the JSON output, no other text or explanation."""

        return prompt
    
    def _call_ollama(self, prompt):
        """Call Ollama API to analyze the screenplay"""
        
        try:
            # Use ollama run command
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
                
                # Try to extract JSON from the output
                # Sometimes Ollama adds extra text, so we need to find the JSON part
                json_start = output.find('{')
                json_end = output.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = output[json_start:json_end]
                    parsed_result = json.loads(json_str)
                    return parsed_result
                else:
                    print("⚠️ Could not find JSON in response")
                    print("Raw output:", output[:200])
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
    
    def validate_assets(self, result):
        """
        Validate that requested GLB files exist in the asset library
        Returns dict with 'available' and 'missing' lists
        """
        
        validation = {
            "available": [],
            "missing": []
        }
        
        if not result:
            return validation
        
        # Collect all requested GLBs
        all_requests = []
        
        # From characters
        for char in result.get('characters', []):
            glb = char.get('suggested_glb', '')
            if glb:
                all_requests.append({
                    'type': 'character',
                    'name': char.get('name'),
                    'description': char.get('description', ''),
                    'glb': glb
                })
        
        # From props
        for prop in result.get('props', []):
            glb = prop.get('suggested_glb', '')
            if glb:
                all_requests.append({
                    'type': 'prop',
                    'name': prop.get('name'),
                    'description': prop.get('description', ''),
                    'glb': glb
                })
        
        # From environment objects
        for obj in result.get('environment_objects', []):
            glb = obj.get('suggested_glb', '')
            if glb:
                all_requests.append({
                    'type': 'environment',
                    'name': obj.get('name'),
                    'count': obj.get('count', 1),
                    'glb': glb
                })
        
        # Check each GLB against asset library
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
        
        # Extract pack name and filename from path
        # e.g., "Ultimate House Interior Pack-glb/Bathtub.glb"
        if '/' in glb_path:
            pack_name, filename = glb_path.rsplit('/', 1)
        else:
            return False
        
        # Check if pack exists and contains the file
        pack_assets = self.asset_info['packs'].get(pack_name, [])
        return filename in pack_assets
    
    def save_missing_assets_report(self, validation, output_file="newAssetsNeeded.txt"):
        """Append missing assets report to file (newer entries at top)"""
        
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
            new_entry.append("NEW ASSETS NEEDED - LATEST ENTRY\n")
            new_entry.append("=" * 60 + "\n\n")
            new_entry.append(f"Total missing assets: {len(validation['missing'])}\n")
            new_entry.append(f"Date: {self._get_timestamp()}\n\n")
            
            # Group by type
            by_type = {'character': [], 'prop': [], 'environment': []}
            for item in validation['missing']:
                item_type = item.get('type', 'unknown')
                if item_type in by_type:
                    by_type[item_type].append(item)
            
            # Write characters
            if by_type['character']:
                new_entry.append("\n" + "=" * 60 + "\n")
                new_entry.append("MISSING CHARACTERS\n")
                new_entry.append("=" * 60 + "\n")
                for item in by_type['character']:
                    new_entry.append(f"\n• {item['name']}\n")
                    if item['description']:
                        new_entry.append(f"  Description: {item['description']}\n")
                    new_entry.append(f"  Requested path: {item['glb']}\n")
                    new_entry.append(f"  Action needed: Create or find character model\n")
            
            # Write props
            if by_type['prop']:
                new_entry.append("\n" + "=" * 60 + "\n")
                new_entry.append("MISSING PROPS\n")
                new_entry.append("=" * 60 + "\n")
                for item in by_type['prop']:
                    new_entry.append(f"\n• {item['name']}\n")
                    if item['description']:
                        new_entry.append(f"  Description: {item['description']}\n")
                    new_entry.append(f"  Requested path: {item['glb']}\n")
                    new_entry.append(f"  Action needed: Create or find prop model\n")
            
            # Write environment objects
            if by_type['environment']:
                new_entry.append("\n" + "=" * 60 + "\n")
                new_entry.append("MISSING ENVIRONMENT OBJECTS\n")
                new_entry.append("=" * 60 + "\n")
                for item in by_type['environment']:
                    count = item.get('count', 1)
                    new_entry.append(f"\n• {item['name']} (needed: {count}x)\n")
                    new_entry.append(f"  Requested path: {item['glb']}\n")
                    new_entry.append(f"  Action needed: Create or find environment asset\n")
            
            # Summary
            new_entry.append("\n" + "=" * 60 + "\n")
            new_entry.append("RECOMMENDATIONS\n")
            new_entry.append("=" * 60 + "\n")
            new_entry.append("1. Search for similar assets in existing packs\n")
            new_entry.append("2. Download/purchase missing asset packs\n")
            new_entry.append("3. Create custom models for unique items\n")
            new_entry.append("4. Use placeholder cubes temporarily\n")
            new_entry.append("\n")
            
            # Add separator between entries
            new_entry.append("\n" + "#" * 60 + "\n")
            new_entry.append("# PREVIOUS ENTRIES BELOW\n")
            new_entry.append("#" * 60 + "\n\n")
            
            # Write new entry at top, then existing content
            with open(output_file, 'w') as f:
                f.write("".join(new_entry))
                if existing_content:
                    # Keep the CURRENT entry as "previous entry" for next time
                    # Find where "PREVIOUS ENTRIES BELOW" starts
                    if "# PREVIOUS ENTRIES BELOW" in existing_content:
                        # Split and keep the part BEFORE the separator AND everything after
                        marker_pos = existing_content.find("\n############################################################\n# PREVIOUS ENTRIES BELOW")
                        if marker_pos > 0:
                            # Get the content before the "PREVIOUS ENTRIES BELOW" marker
                            current_entry = existing_content[:marker_pos].strip()
                            # Write it as a previous entry
                            f.write(current_entry + "\n\n")
                            
                            # Now get any actual old entries that were after the marker
                            parts = existing_content.split("# PREVIOUS ENTRIES BELOW\n", 1)
                            if len(parts) > 1:
                                old_entries = parts[1]
                                # Skip the separator line (####...)
                                lines = old_entries.split('\n')
                                start_idx = 0
                                if lines and lines[0].startswith('#' * 10):
                                    start_idx = 1
                                # Skip leading empty lines
                                while start_idx < len(lines) and not lines[start_idx].strip():
                                    start_idx += 1
                                # Write old entries if any exist
                                if start_idx < len(lines):
                                    remaining = '\n'.join(lines[start_idx:]).strip()
                                    if remaining:
                                        f.write(remaining + "\n")
                    else:
                        # No marker exists - this is very old format, just append it all
                        f.write(existing_content)
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving missing assets report: {e}")
            return False
    
    def _get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def display_results(self, result, validation=None):
        """Display the parsed results in a nice format"""
        
        if not result:
            return
        
        print("\n" + "=" * 50)
        print("📋 REQUIRED GLB FILES")
        print("=" * 50)
        
        print(f"\n📍 LOCATION: {result.get('location', 'Unknown')}")
        print(f"🎬 SCENE TYPE: {result.get('environment_type', 'Unknown')}")
        
        # Helper to get status icon
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
        
        print("\n👥 CHARACTERS:")
        characters = result.get('characters', [])
        if characters:
            for i, char in enumerate(characters, 1):
                status = get_status(char.get('suggested_glb', ''))
                print(f"   {i}. {status} {char.get('name', 'Unknown')}")
                print(f"      Description: {char.get('description', 'N/A')}")
                print(f"      GLB: {char.get('suggested_glb', 'Not found')}")
        else:
            print("   (None)")
        
        print("\n🎭 PROPS:")
        props = result.get('props', [])
        if props:
            for i, prop in enumerate(props, 1):
                status = get_status(prop.get('suggested_glb', ''))
                print(f"   {i}. {status} {prop.get('name', 'Unknown')}")
                print(f"      Description: {prop.get('description', 'N/A')}")
                print(f"      GLB: {prop.get('suggested_glb', 'Not found')}")
        else:
            print("   (None)")
        
        print("\n🌍 ENVIRONMENT OBJECTS:")
        env_objects = result.get('environment_objects', [])
        if env_objects:
            for i, obj in enumerate(env_objects, 1):
                count = obj.get('count', 1)
                status = get_status(obj.get('suggested_glb', ''))
                print(f"   {i}. {status} {obj.get('name', 'Unknown')} (x{count})")
                print(f"      GLB: {obj.get('suggested_glb', 'Not found')}")
        else:
            print("   (None)")
        
        # Summary of all GLB files needed
        print("\n" + "=" * 50)
        print("📦 SUMMARY - ALL GLB FILES NEEDED:")
        print("=" * 50)
        
        all_glbs = []
        for char in characters:
            glb = char.get('suggested_glb')
            if glb:
                all_glbs.append(glb)
        
        for prop in props:
            glb = prop.get('suggested_glb')
            if glb:
                all_glbs.append(glb)
        
        for obj in env_objects:
            glb = obj.get('suggested_glb')
            if glb:
                count = obj.get('count', 1)
                all_glbs.extend([glb] * count)
        
        if all_glbs:
            for i, glb in enumerate(all_glbs, 1):
                status = get_status(glb)
                print(f"   {i}. {status} {glb}")
        else:
            print("   (None found)")
        
        print(f"\n✅ Total GLB files needed: {len(all_glbs)}")
        
        # Validation summary
        if validation:
            print("\n" + "=" * 50)
            print("🔍 ASSET VALIDATION:")
            print("=" * 50)
            print(f"✅ Available in library: {len(validation['available'])}")
            print(f"❌ Missing from library: {len(validation['missing'])}")
            
            if validation['missing']:
                print("\n⚠️  WARNING: Some assets are not in the library!")
                print("   A detailed report will be saved to 'newAssetsNeeded.txt'")
    
    def save_results(self, result, output_file="required_glbs.json"):
        """Save the results to a JSON file"""
        
        if not result:
            return False
        
        try:
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n💾 Results saved to: {output_file}")
            return True
        except Exception as e:
            print(f"❌ Failed to save results: {e}")
            return False

def main():
    """Example usage of the screenplay parser with validation"""
    
    # Example screenplay with some missing assets (dragon, phone charger)
    screenplay = """
    EXT. CASTLE - DAY
    
    A DRAGON flies overhead, breathing fire.
    
    RICK, a young man in beach attire, watches from below.
    He picks up his PHONE CHARGER from the ground.
    """
    
    print("🎬 SCREENPLAY PARSER - STEP 1 (with Asset Validation)")
    print("=" * 50)
    print("\n📝 Example Screenplay:")
    print(screenplay)
    
    parser = ScreenplayParser()
    result = parser.parse_screenplay(screenplay)
    
    if result:
        # Validate assets against library
        validation = parser.validate_assets(result)
        
        # Display results with validation status
        parser.display_results(result, validation)
        parser.save_results(result)
        
        # Save missing assets report if needed
        if validation['missing']:
            parser.save_missing_assets_report(validation)
            print("\n📝 Missing assets report saved: newAssetsNeeded.txt")
        
        print("\n✅ Step 1 Complete!")
        print("💡 Next step: Use these GLB files to generate the scene")
    else:
        print("\n❌ Failed to parse screenplay")

if __name__ == "__main__":
    main()
