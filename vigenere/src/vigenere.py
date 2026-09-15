import sys
import argparse
from pathlib import Path
from collections import defaultdict
from unidecode import unidecode

import numpy as np
import pandas as pd


alphabets = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
char_idx = {
    char : idx
    for idx, char in enumerate(alphabets)
}

e_ioc = 0.067
e_freqs = (
    pd.read_csv("./letter_freq.txt")
    .set_index("letter")["frequency"]
    .to_dict()
)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def read_file(fname):
    with open(fname, "r") as fin:
        content = fin.read()
    return content


def normalize_text(text):
    return (''.join([char for char in unidecode(text) if char.isalpha()])).upper()


def pad_key(text, key):
    tlen, klen = len(text), len(key)
    rep = tlen // klen
    remainder = tlen % klen

    return key * rep + key[:remainder]


def encrypt_decrypt(mode, input, key):
    if mode == "encrypt":
        sign = 1
    else:
        sign = -1

    padded_key = pad_key(input, key)

    output = ""
    for input_char, key_char in zip(input, padded_key):
        input_idx, key_idx = char_idx[input_char], char_idx[key_char]
        output_char = alphabets[(input_idx + (sign * key_idx)) % 26]
        output += output_char

    return output


def build_matrix(text, klen):
    """
    Fit text into a matrix whose width is key length. 
    Empty slots are filled with NULL which are
    """
    n = len(text)
    padded_text = list(text)
    padding_len = int((np.ceil(n / klen) * klen) - n)
    if padding_len != 0:
        padded_text.extend([None] * padding_len)

    matrix = np.reshape(padded_text, shape=(-1, klen))

    return matrix


def ioc(column):
    """
    Calculate index of coincidence for the given matrix column. 
    """
    counts = {char : 0 for char in alphabets}
    for char in column:
        if char == None: continue
        counts[char] += 1
    
    n = len(column)
    numerator = sum(
        n_i * (n_i - 1)
        for n_i in counts.values()
    )
    denominator = n * (n - 1)
    ioc = numerator / denominator

    return ioc


def guess_key_length(cipher, alpha=0.7):
    """
    For each possible key length (1-32), build a cipher matrix;
    Calculate the per-column IOCs for each matrix;
    Compute an average IOC score over the columns and rank them (the closer to the 
    real English IOC, the better);
    With the ranked key-length-to-IOCs-mapping (top 5), we pick the one that best
    balances IOC differences and key length. 
    """

    klen_ioc_diff = defaultdict(float)
    for klen in range(1, min(32, len(cipher)//2)+1):
        ioc_sum = 0.0
        matrix = build_matrix(cipher, klen)
        ioc_sum = sum( ioc(matrix[:,i]) for i in range(klen) )
        avg_ioc = ioc_sum / klen
        klen_ioc_diff[klen] = abs(avg_ioc - e_ioc)

    top_klen_ioc_diff = {
        klen : ioc_diff
        for klen, ioc_diff in sorted(klen_ioc_diff.items(), key=lambda x: x[1])[:5]
    }

    ranked_klen = top_klen_ioc_diff.keys()
    best_score, best_klen = float('-inf'), list(ranked_klen)[0]
    max_diff = max(klen_ioc_diff.values())

    for klen, ioc_diff in top_klen_ioc_diff.items():
        # ioc score
        ico_score = 1 - (ioc_diff / max_diff)

        # length score (better when more candidates are its multiples)
        rest = ranked_klen - {klen}
        dividing_count = sum( (1 - 1/r) for r in rest if r % klen == 0 )
        divisor_score = dividing_count / len(rest)

        # combined score
        final_score = alpha * ico_score + (1 - alpha) * divisor_score

        if final_score > best_score:
            best_score, best_klen = final_score, klen

    return best_klen


def chi_squared(counts, e_counts):
    """
    Measure how similar two probability distributions are to each other.
    Close to 0 when identical.
    Go higher when more different. 
    """
    terms = []
    for c, e in zip(counts, e_counts):
        if e == 0:
            terms.append(0)
            continue
        terms.append( ((c - e) ** 2) / e )

    return sum(terms)


def deduplicate_key(key):
    """
    If the key has repetition of smaller unit within, 
    truncate the redundant part and report modified key.  
    """
    klen = len(key)
    if klen <= 3: return key

    for i in range(1, klen):
        rotated_key = key[i:] + key[:i]
        if rotated_key == key: 
            return key[:i]
        
    return key


def guess_shifts(column):
    """
    Column-shift scoring function.
    Use Chi Squared method to test how similar the guess-shift-distribution is
    to the actual distribution (lower means more similar).
    Return a list of possible key characters (ordered from most to least likely). 
    """
    n = len(column)
    o_counts = { char : 0 for char in alphabets }
    for char in column:
        if char == None: continue
        o_counts[char] += 1

    shift_scores = { i : float('inf') for i in range(26) } 
    for shift in range(0, 26):
        e_counts = { char : 0 for char in alphabets }
        for cipher_char in o_counts.keys():
            guessed_char = alphabets[(char_idx[cipher_char] - shift) % 26]
            e_counts[cipher_char] = (e_freqs[guessed_char] / 100) * n 
        shift_scores[shift] = chi_squared(o_counts.values(), e_counts.values())

    ordered_guesses = [
        alphabets[shift]
        for shift, _ in sorted(shift_scores.items(), key=lambda x:x[1])
    ]

    return ordered_guesses


def guess_keys(cipher, klen):
    """
    Guess key by Kerckhoff method. 
    """
    matrix = build_matrix(cipher, klen)
    
    all_ordered_guesses = []
    for i in range(klen):
        ordered_guesses_col_i = guess_shifts(matrix[:,i])
        all_ordered_guesses.append(ordered_guesses_col_i)

    keys = [
        "".join(col_guesses[rank] for col_guesses in all_ordered_guesses)
        for rank in range(len(all_ordered_guesses[0]))
    ]

    return [
        deduplicate_key(k)
        for k in keys
    ]


def run(mode):

    parser = argparse.ArgumentParser()
    if mode in ("encrypt", "decrypt"):
        parser.add_argument("key", type=str)
        parser.add_argument("fname", type=str)
    elif mode == "keylength": 
        parser.add_argument("fname", type=str)
    else:
        parser.add_argument("fname", type=str)
        parser.add_argument("keylen", type=int)
    args = parser.parse_args()

    input_text = normalize_text(read_file(args.fname))

    if mode in ("encrypt", "decrypt"):
        if Path(args.key).is_file():
            key = normalize_text(read_file(args.key))
        else: 
            key = normalize_text(args.key)

        if len(key) == 0 or len(key) > 32:
            print("Key length invalid (1-32 characters)")
            sys.exit()

        output_text = encrypt_decrypt(mode, input_text, key)
        print(output_text)

    elif mode == "keylength":
        recovered_length = guess_key_length(input_text)
        print(recovered_length)
    
    elif mode == "cryptanalyze":
        if args.keylen < 1 or args.keylen > 32:
            eprint("Key length invalid (1-32 characters)")
            sys.exit(1)
        keys = guess_keys(input_text, args.keylen)
        for k in keys[:10]:
            print(k)

    else: 
        eprint(f"Invalid mode: {mode}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        eprint("Usage: vigenere.py <encrypt|decrypt|keylength|cryptanalyze|break> [args...]")
        sys.exit(1)
    mode = sys.argv[1]
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    run(mode)