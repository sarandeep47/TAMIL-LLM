
class TamilTokenizer:
    def __init__(self, text):
        self.chars = sorted(set(text))
        self.char_to_id = {
            char: index for index, char in enumerate(self.chars)
        }
        self.id_to_char = {
            index: char for char, index in self.char_to_id.items()
        }

    def encode(self, text):
        return [self.char_to_id[char] for char in text
                if char in self.char_to_id]

    def decode(self, ids):
        return "".join(self.id_to_char[i] for i in ids)
