import wave
import struct
import math

def generate_beep(filename, frequency, duration, volume=0.5, sample_rate=44100):
    num_samples = int(duration * sample_rate)
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 2 bytes per sample
        wav_file.setframerate(sample_rate)
        
        for i in range(num_samples):
            # Apply a simple envelope to avoid clicks
            envelope = 1.0
            if i < 100:
                envelope = i / 100
            elif i > num_samples - 100:
                envelope = (num_samples - i) / 100
                
            value = int(volume * envelope * 32767.0 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)

# Generate move sound: a low frequency thud-like sound
generate_beep('assets/move.wav', 200, 0.1, volume=0.3)

# Generate capture sound: a slightly higher frequency click
generate_beep('assets/capture.wav', 400, 0.1, volume=0.4)

print("Sound files generated in assets folder.")
