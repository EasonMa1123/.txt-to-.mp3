import os
import soundfile as sf
import numpy as np
import re
import asyncio
import edge_tts
from pathlib import Path
from deep_translator import GoogleTranslator

# Global registry to hold automatically detected character profiles
DYNAMIC_VOICE_PROFILES = {}

def analyze_and_register_characters(content):
    """
    Scans the script to auto-detect all unique characters and dynamically
    assigns them a Cantonese voice profile based on age and gender keywords.
    """
    global DYNAMIC_VOICE_PROFILES
    DYNAMIC_VOICE_PROFILES.clear()
    
    # Find all unique character names before the "：" separator
    detected_names = set(re.findall(r'([^：\n]+)：', content))
    # Remove '旁白' (Narrator) from dynamic assignment since it's a fixed standard
    detected_names.discard('旁白')
    
    print(f"\n[AUTO-DETECT] Found {len(detected_names)} unique characters in script: {list(detected_names)}")
    
    # Lists of available base Cantonese neural voices to cycle through
    female_pool = ["zh-HK-HiuGaaiNeural", "zh-HK-HiuMaanNeural", "zh-HK-HiuYanNeural"]
    male_pool = ["zh-HK-WanLungNeural"]
    
    f_idx, m_idx = 0, 0
    
    for name in sorted(list(detected_names)):
        name_strip = name.strip()
        
        # 1. Determine Gender (Default to Female if ambiguous)
        is_male = any(kw in name_strip for kw in ['爸爸', '爺爺', '公公', '叔', '伯', '仔', '兄', '弟', '男', '豪', '明'])
        
        # 2. Determine Age Group (Child, Old, or Default Adult)
        if any(kw in name_strip for kw in ['仔', '女', '家家', '蘋', '小', '童', '兒']):
            age = "child"
        elif any(kw in name_strip for kw in ['爺', '嫲', '婆', '公', '老', '伯']):
            age = "old"
        else:
            age = "adult"
            
        # 3. Assign Base Voice and Custom Pitch Adjustments
        if is_male:
            # Cycle through male pool (or reuse if pool size exhausted)
            base_voice = male_pool[m_idx % len(male_pool)]
            m_idx += 1
            # Adjust pitch based on age rules
            pitch = "+45Hz" if age == "child" else ("-25Hz" if age == "old" else "+0Hz")
        else:
            base_voice = female_pool[f_idx % len(female_pool)]
            f_idx += 1
            # Adjust pitch based on age rules
            pitch = "+35Hz" if age == "child" else ("-20Hz" if age == "old" else "+0Hz")
            
        DYNAMIC_VOICE_PROFILES[name_strip] = {
            "voice": base_voice,
            "pitch": pitch,
            "gender": "Male" if is_male else "Female",
            "age": age
        }
        print(f"  -> Profile Assigned | {name_strip}: Gender={DYNAMIC_VOICE_PROFILES[name_strip]['gender']}, Age={age} -> Voice={base_voice}, Pitch={pitch}")

def get_character_voice_profile(character):
    """Retrieve the automatically generated profile or fallback to Narrator profile."""
    if character == '旁白':
        return {"voice": "zh-HK-HiuMaanNeural", "pitch": "+0Hz"}
    
    return DYNAMIC_VOICE_PROFILES.get(character, {"voice": "zh-HK-HiuGaaiNeural", "pitch": "+0Hz"})

def get_character_code(character):
    """Automatically translates Chinese character names to safe English filename codes."""
    if character == '旁白':
        return 'narrator'
        
    try:
        # Translate name to English via a free Google Translate scrap-less layer
        translated = GoogleTranslator(source='auto', target='en').translate(character)
        # Clean up string text to make it safe for standard filenames
        clean_code = re.sub(r'[^a-zA-Z0-True]', '', translated).lower()
        return clean_code if clean_code else "character"
    except Exception as e:
        print(f"[Warning] Translation failed for {character}: {e}. Using raw string hashes.")
        return str(hash(character))

async def create_voice(text, output_file, voice_profile):
    """Create a voice file for the given text using edge-tts, with retry."""
    MAX_RETRY = 10
    voice = voice_profile["voice"]
    pitch = voice_profile["pitch"]

    for attempt in range(1, MAX_RETRY + 1):
        try:
            communicate = edge_tts.Communicate(text, voice, rate="-30%", pitch=pitch)
            await communicate.save(output_file)
            print(f"[OK] Created: {output_file}  (Voice={voice}, Pitch={pitch})")
            return True
        except Exception as e:
            print(f"[ERROR {attempt}] Voice failed ({voice}): {e}")
            await asyncio.sleep(0.8 * attempt)
    return False

def combine_audio_files(input_files, output_file):
    """Combine multiple audio files into one using soundfile."""
    try:
        print("\nStarting audio combination process...")
        data, samplerate = sf.read(input_files[0])
        combined_data = data
        
        for i, file in enumerate(input_files[1:], 1):
            try:
                data, _ = sf.read(file)
                silence = np.zeros(int(samplerate * 0.5))
                combined_data = np.concatenate([combined_data, silence, data])
            except Exception as e:
                print(f"Error processing file {file}: {e}")
                continue
        
        sf.write(output_file, combined_data, samplerate)
        print(f"Combined audio saved successfully to {output_file}")
        return True
    except Exception as e:
        print(f"Error combining audio files: {e}")
        return False

async def process_text_file(input_file):
    """Process the text file, extract characters dynamically, and generate sequence assets."""
    try:
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)

        # Cleanup matching legacy audio structures
        for file in output_dir.glob('*.wav'):
            try:
                file.unlink()
            except Exception:
                pass

        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Step 1: Automatically analyze text to parse out actors & build properties matrix
        analyze_and_register_characters(content)

        scenes = [scene.strip() for scene in content.split('\n\n') if scene.strip()]
        temp_files = []
        
        for scene_num, scene in enumerate(scenes, 1):
            print(f"\nProcessing Scene {scene_num}")
            
            # Identify individual structural elements lines chronologically 
            lines = re.findall(r'([^：\n]+)：(.*?)(?=\n|$)', scene)
            char_dialogue_count = {}
            
            for character, text in lines:
                character = character.strip()
                text = text.strip()
                
                char_dialogue_count[character] = char_dialogue_count.get(character, 0) + 1
                dialogue_num = char_dialogue_count[character]
                
                char_code = get_character_code(character)
                temp_file = output_dir / f'temp_{char_code}_{scene_num}_{dialogue_num}.wav'
                
                profile = get_character_voice_profile(character)
                if await create_voice(text, str(temp_file), profile):
                    temp_files.append(temp_file)
                
                await asyncio.sleep(0.4)
        
        if not temp_files:
            print("No audio files were created successfully.")
            return
        
        output_file = output_dir / 'complete_audio.wav'
        if combine_audio_files([str(f) for f in temp_files], str(output_file)):
            for temp_file in temp_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception:
                    pass
            print("Temporary split assets successfully cleared.")
            
    except Exception as e:
        print(f"Error processing text file: {e}")

async def main():
    try:
        input_file = "script.txt"
        if not os.path.exists(input_file):
            print("File not found!")
            return
        await process_text_file(input_file)
        print("\nProcessing complete! Check 'output/complete_audio.wav'")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())