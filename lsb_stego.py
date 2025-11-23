import wave
import os

def encode_lsb(input_path, output_path, secret_message):
    """
    Вбудовує приховане текстове повідомлення у аудіофайл формату WAV методом LSB.

    Функція конвертує рядок повідомлення у бінарну послідовність, додає спеціальний
    маркер закінчення ('#####END') та замінює найменші значущі біти (Least Significant Bits)
    аудіоданих на біти повідомлення.

    :param input_path: Шлях до вхідного незахищеного файлу (.wav).
    :type input_path: str
    :param output_path: Шлях, куди буде збережено захищений файл.
    :type output_path: str
    :param secret_message: Унікальний рядок (Payload), який потрібно сховати (наприклад, ISRC або ID власника).
    :type secret_message: str
    
    :return: True, якщо вбудовування пройшло успішно, інакше False.
    :rtype: bool
    
    :raises ValueError: Якщо розмір аудіофайлу занадто малий для вміщення повідомлення.
    :raises Exception: При помилках відкриття файлу або запису.
    """
    try:
        song = wave.open(input_path, mode='rb')
        frame_bytes = bytearray(list(song.readframes(song.getnframes())))
        
        full_message = secret_message + '#####END'
        
        bits = ''.join([bin(ord(x))[2:].zfill(8) for x in full_message])
        bits_list = [int(b) for b in bits]
        
        if len(bits_list) > len(frame_bytes):
            raise ValueError("Файл занадто малий для цього повідомлення!")
        
        for i, bit in enumerate(bits_list):
            frame_bytes[i] = (frame_bytes[i] & 254) | bit
            
        modified_frames = bytes(frame_bytes)
        with wave.open(output_path, 'wb') as fd:
            fd.setparams(song.getparams())
            fd.writeframes(modified_frames)
        
        song.close()
        return True
    except Exception as e:
        print(f"LSB Encode Error: {e}")
        return False

def decode_lsb(file_path):
    """
    Витягує та декодує приховане повідомлення із захищеного WAV-файлу.

    Функція зчитує LSB (найменші значущі біти) з кожного байту аудіоданих,
    формує з них символи та шукає маркер закінчення ('#####END').

    :param file_path: Шлях до файлу (.wav), який потрібно перевірити.
    :type file_path: str
    
    :return: Розшифрований рядок повідомлення (без маркера), якщо його знайдено.
             Повертає None, якщо маркер не знайдено або файл не містить прихованих даних.
    :rtype: str | None
    
    :raises Exception: При помилках читання файлу.
    """
    try:
        song = wave.open(file_path, mode='rb')
        frame_bytes = bytearray(list(song.readframes(song.getnframes())))
        
        # Витягуємо LSB
        extracted_bits = [frame_bytes[i] & 1 for i in range(len(frame_bytes))]
        
        chars = []
        for i in range(0, len(extracted_bits), 8):
            byte = extracted_bits[i:i+8]
            if len(byte) < 8: break
            
            char_code = int(''.join(map(str, byte)), 2)
            chars.append(chr(char_code))
            
            # Перевіряємо маркер кінця
            if len(chars) >= 8 and ''.join(chars[-8:]) == '#####END':
                song.close()
                return ''.join(chars[:-8]) # Повертаємо текст без маркера
                
        song.close()
        return None
    except Exception as e:
        print(f"LSB Decode Error: {e}")
        return None