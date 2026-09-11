import argparse
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

OUTDIR = "output"
Path(OUTDIR).mkdir(parents=True, exist_ok=True)

alphabets = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
char_idx = {
    char : idx
    for idx, char in enumerate(alphabets)
}
freqs = (
    pd.read_csv("./letter_freq.txt")
    .sort_values("frequency", ascending=False)
)
e_freqs = {
    letter : freq
    for letter, freq in zip(freqs['letter'], freqs['frequency'])
}


def write_file(fname, text):
    with open(f"{OUTDIR}/{fname}.txt", "w") as fout: 
        fout.write(text)


def normalize_text(text):
    return (''.join([char for char in text if char.isalpha()])).upper()


def pad_key(text, key):
    tlen, klen = len(text), len(key)
    rep = tlen // klen
    remainder = tlen % klen

    return key * rep + key[:remainder]


def encrypt_decrypt(mode, input, key):
    if mode == "encrypt":
        m = 1
        fout = f"ciphertext-{key}"
    else:
        m = -1
        fout = f"recovered-{key}"

    padded_key = pad_key(input, key)
    output = ""
    for input_char, key_char in zip(input, padded_key):
        input_idx = char_idx[input_char]
        key_idx = char_idx[key_char]
        output_char = alphabets[(input_idx + (m * key_idx)) % 26]
        output += output_char

    write_file(fout, output)

    return output


def ioc(column):
    """
    Calculate index of coincidence for one matrix column. 
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


def friedman(cipher):
    """
    Give each possible key length (1-32) a score of likelihood.
    Return best guess (a integer). 
    """
    clen = len(cipher)
    
    klen_score = defaultdict(int)
    for klen in range(1, min(32, clen//2)+1):
        curr_score = 0.0
        matrix = build_matrix(cipher, klen)
        for i in range(klen):
            curr_score += ioc(matrix[:,i])
        klen_score[klen] = curr_score / klen
    
    sorted_klen_score = sorted(
        klen_score.items(),
        key=lambda x:x[1],reverse=True
    )
    
    return sorted_klen_score[0][0]


def kasiski(cipher):
    size = 3
    clen = len(cipher)
    chunk_to_idxs = defaultdict(list)
    for i in range(0, clen - size + 1):
        chunk = cipher[i:i+size]
        chunk_to_idxs[chunk].append(i)

    intervals = []
    for chunk, idxs in chunk_to_idxs.items():
        occurrence = len(idxs)
        if occurrence == 1: continue
        for i in range(occurrence):
            for j in range(i+1, occurrence):
                intervals.append(idxs[j] - idxs[i])
    
    klen_to_score = defaultdict(int)
    for interval in intervals:
        for klen in range(2, min(32, clen//2)+1):
            if interval % klen == 0:
                klen_to_score[klen] += 1
    
    sorted_klen_to_score = sorted(
        klen_to_score.items(),
        key=lambda x:x[1], reverse=True
    )

    return sorted_klen_to_score[0][0]


def guess_key_length(cipher):
    """
    Use Friedman's statistical method to estimate key length. 
    """
    friedman_guess = friedman(cipher)
    # kasiski_guess = kasiski(cipher)
    return friedman_guess


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


def print_candidate_keys(ordered_guessed_per_column, top_n):
    """
    Print top most likely keys. 
    Return nothing. 
    """
    for i in range(top_n):
        key = ""
        for col in ordered_guessed_per_column:
            key += col[i]
        print(key)


def build_matrix(text, klen):
    """
    Fit text into a matrix whose width is key length.
    Empty slots are filled with 'None'.
    Return matrix. 
    """
    n = len(text)
    padded_text = list(text)
    padding_len = int((np.ceil(n / klen) * klen) - n)
    if padding_len != 0:
        padded_text.extend([None] * padding_len)

    matrix = np.reshape(padded_text, shape=(-1, klen))

    return matrix


def kerckhoff(column):
    """
    Column-shift scoring function.
    Use Chi Squared method to test how similar the guess-shift-distribution is
    to the actual distribution (lower means more similar).
    Return a list of possible key characters (ordered from most to least likely). 
    """
    n = len(column)
    counts = { char : 0 for char in alphabets }
    for char in column:
        if char == None: continue
        counts[char] += 1

    shift_scores = { i : float('inf') for i in range(26) } 
    for shift in range(0, 26):
        e_counts = { char : 0 for char in alphabets }
        for cipher_char in counts.keys():
            guessed_char = alphabets[(char_idx[cipher_char] - shift) % 26]
            e_counts[cipher_char] = (e_freqs[guessed_char] / 100) * n 
        shift_scores[shift] = chi_squared(counts.values(), e_counts.values())

    ordered_guesses = [
        alphabets[shift]
        for shift, _ in sorted(shift_scores.items(), key=lambda x:x[1])
    ]

    return ordered_guesses


def guess_key(cipher, klen):
    """
    Guess key by Kerckhoff method. 
    """
    matrix = build_matrix(cipher, klen)
    
    ordered_guessed_per_column = []
    for i in range(klen):
        ordered_guessed_per_column.append(kerckhoff(matrix[:,i]))

    return ordered_guessed_per_column


def run(mode):

    parser = argparse.ArgumentParser()
    if mode == ("encrypt" or "decrypt"):
        parser.add_argument("key", type=str) 
    parser.add_argument("fname", type=str)
    args = parser.parse_args()

    with open(args.fname) as fin:
        content = fin.read()
    input_text = normalize_text(content)

    if mode == ("encrypt" or "decrypt"):
        if Path(args.key).is_file():
            with open(args.key) as fin:
                content = fin.read()
            key = normalize_text(content)
        else: 
            key = normalize_text(args.key)

        if len(key) == 0 or len(key) > 32:
            print("Key length invalid (1-32 characters)")
            exit()

        output_text = encrypt_decrypt(mode, input_text, key)
        print(output_text)

    elif mode == "keylength":
        recovered_length = guess_key_length(input_text)
        print(recovered_length)
    
    elif mode == "cryptanalyze":
        recovered_length = guess_key_length(input_text)
        ordered_guessed_per_column = guess_key(input_text, recovered_length)
        print_candidate_keys(ordered_guessed_per_column, 10)
    
    else: 
        print("Invalid mode. Try again.")