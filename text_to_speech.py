import os
import soundfile as sf
import numpy as np
import re
import asyncio
import edge_tts
from pathlib import Path

def get_character_voice(character):
    """Get the appropriate voice for each character."""
    voice_map = {
        '旁白': "zh-HK-HiuMaanNeural",  # Female voice 1 for narrator
        '李蘋': "zh-HK-HiuGaaiNeural",  # Female voice 2 for Li Ping
        '爸爸': "zh-HK-WanLungNeural",  # Male voice for father
        '王小明': "zh-HK-HiuGaaiNeural",  # Female voice 1 for Xiao Ming
        '媽媽': "zh-HK-HiuYanNeural"   # Using HiuGaaiNeural for mother instead of YanNeural
    }
    return voice_map.get(character, "zh-HK-HiuGaaiNeural")

async def create_voice(text, output_file, voice):
    """Create a voice file for the given text using edge-tts, with retry."""
    MAX_RETRY = 10

    for attempt in range(1, MAX_RETRY + 1):
        try:
            communicate = edge_tts.Communicate(text, voice, rate="-30%")
            await communicate.save(output_file)
            print(f"[OK] Created: {output_file}  (Voice={voice})")
            return True

        except Exception as e:
            print(f"[ERROR {attempt}] Voice failed ({voice}): {e}")

            # 403 -- likely rate-limit → wait & retry
            await asyncio.sleep(0.8 * attempt)

            # try fallback Cantonese voices
            fallback_voices = [
                "zh-HK-HiuGaaiNeural",
                "zh-HK-HiuMaanNeural",
                "zh-HK-WanLungNeural"
            ]

            for fallback in fallback_voices:
                if fallback != voice:
                    try:
                        print(f"Retrying with fallback: {fallback}")
                        communicate = edge_tts.Communicate(text, fallback, rate="-30%")
                        await communicate.save(output_file)
                        print(f"[OK] Fallback created: {output_file} (Voice={fallback})")
                        return True
                    except:
                        continue

    print(f"[FAILED] Could not synthesize after {MAX_RETRY} attempts.")
    return False

def combine_audio_files(input_files, output_file):
    """Combine multiple audio files into one."""
    try:
        print("\nStarting audio combination process...")
        print(f"Input files to combine: {input_files}")
        
        # Read the first file to get the sample rate
        print(f"Reading first file: {input_files[0]}")
        data, samplerate = sf.read(input_files[0])
        combined_data = data
        print(f"First file read successfully. Sample rate: {samplerate}")
        
        # Read and concatenate the rest of the files
        for i, file in enumerate(input_files[1:], 1):
            try:
                print(f"\nProcessing file {i+1}/{len(input_files)}: {file}")
                data, _ = sf.read(file)
                # Add 0.5 seconds of silence (samplerate/2 samples)
                silence = np.zeros(int(samplerate * 0.5))
                combined_data = np.concatenate([combined_data, silence, data])
                print(f"Successfully added file {file} to combined audio")
            except Exception as e:
                print(f"Error processing file {file}: {e}")
                continue
        
        # Save the combined audio
        print(f"\nSaving combined audio to {output_file}")
        sf.write(output_file, combined_data, samplerate)
        print(f"Combined audio saved successfully to {output_file}")
        return True
    except Exception as e:
        print(f"Error combining audio files: {e}")
        return False

def get_character_code(character):
    """Convert Chinese character names to English codes."""
    character_map = {
        '旁白': 'narrator',
        '李蘋': 'liping',
        '爸爸': 'father',
        '王小明': 'xiaoming',
        '媽媽': 'mother'
    }
    return character_map.get(character, character)

async def process_text_file(input_file):
    """Process the text file and create audio files for each character."""
    try:
        # Create output directory if it doesn't exist
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)

        # Remove previous audio files
        print("Cleaning up previous audio files...")
        for file in output_dir.glob('*.wav'):
            try:
                file.unlink()
                print(f"Removed previous file: {file}")
            except Exception as e:
                print(f"Error removing file {file}: {e}")

        # Read the input file
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split content into scenes (separated by blank lines)
        scenes = [scene.strip() for scene in content.split('\n\n') if scene.strip()]
        temp_files = []  # Keep track of temporary files to delete later
        
        # Process each scene
        for scene_num, scene in enumerate(scenes, 1):
            print(f"\nProcessing Scene {scene_num}")
            print(f"Scene content:\n{scene}\n")
            
            # Extract narrator text
            narrator_text = re.findall(r'旁白：(.*?)(?=\n|$)', scene)
            if narrator_text:
                print(f"Found narrator text: {narrator_text[0]}")
                temp_file = output_dir / f'temp_narrator_{scene_num}_1.wav'
                if await create_voice(narrator_text[0], str(temp_file), 
                                   get_character_voice('旁白')):
                    temp_files.append(temp_file)
                    print(f"Added narrator file: {temp_file}")
            
            # Extract character dialogues
            dialogues = re.findall(r'([^：]+)：(.*?)(?=\n|$)', scene)
            print(f"Found {len(dialogues)} dialogues")
            
            # Keep track of dialogue count for each character in this scene
            char_dialogue_count = {}
            
            for character, text in dialogues:
                character = character.strip()
                if character != '旁白':
                    # Increment dialogue count for this character
                    char_dialogue_count[character] = char_dialogue_count.get(character, 0) + 1
                    dialogue_num = char_dialogue_count[character]
                    
                    print(f"Processing dialogue {dialogue_num} for {character}: {text}")
                    char_code = get_character_code(character)
                    temp_file = output_dir / f'temp_{char_code}_{scene_num}_{dialogue_num}.wav'
                    if await create_voice(text, str(temp_file), 
                                       get_character_voice(character)):
                        temp_files.append(temp_file)
                        print(f"Added {character} file: {temp_file}")
        
        if not temp_files:
            print("No audio files were created successfully.")
            return
        
        print(f"\nTotal files to combine: {len(temp_files)}")
        print("Files to combine:")
        for f in temp_files:
            print(f"  - {f}")
        
        # Combine all audio files
        print("\nCombining all audio files...")
        output_file = output_dir / 'complete_audio.wav'
        if combine_audio_files([str(f) for f in temp_files], str(output_file)):
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                        print(f"Removed temporary file: {temp_file}")
                except Exception as e:
                    print(f"Error removing temporary file {temp_file}: {e}")
            print("Temporary files cleaned up")
        else:
            print("Failed to combine audio files.")
    
    except Exception as e:
        print(f"Error processing text file: {e}")

async def main():
    try:
        input_file = "script.txt"
        if not os.path.exists(input_file):
            print("File not found!")
            return
        
        await process_text_file(input_file)
        print("Processing complete! Check the 'output' directory for the complete_audio.wav file.")
    
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 