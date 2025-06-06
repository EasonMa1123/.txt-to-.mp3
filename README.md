# Text to Speech Converter

This tool converts text files containing dialogues into a single WAV audio file with Cantonese voices for each character using Microsoft Edge's Text-to-Speech service.

## Requirements

- Python 3.6 or higher
- Required Python packages (install using `pip install -r requirements.txt`):
  - edge-tts
  - soundfile
  - numpy

## Installation

1. Clone or download this repository
2. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Prepare your text file with the following format:
```
場景一
旁白：[narrator text]
角色1：[dialogue text]
角色2：[dialogue text]

場景二
旁白：[narrator text]
角色1：[dialogue text]
角色2：[dialogue text]
```

2. Run the script:
```bash
python text_to_speech.py
```

3. When prompted, enter the path to your text file.

4. The script will:
   - Process all dialogues in the text file
   - Create a single WAV file containing all dialogues in sequence
   - Save the file as 'complete_audio.wav' in the 'output' directory

## Output

The script will create:
- A single WAV file ('complete_audio.wav') containing all dialogues
- The file will be saved in the 'output' directory
- Dialogues will be separated by 0.5 seconds of silence

## Notes

- The script uses Microsoft Edge's Text-to-Speech service (edge-tts) for voice generation
- The voice is set to Cantonese (zh-HK-HiuGaaiNeural)
- All dialogues are combined into a single WAV file
- No API key or account required - completely free to use! 