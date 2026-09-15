## Key-length decision rules and Column-scoring statistic

For each possible key length (1-32), build a cipher matrix; for each matrix, we calculate the per-column IOCs and compute an average IOC score over the columns. Now we have an average IOC score for each possible key length. Then, we rank them by how close they are to the real English IOC (IOC difference).  

For the top five candidates key length (I kinda just picked it after eyeballing the scores for all key lengths), we will give each a weighed score on two factors:

1. *IOC closeness*. It measures how close that key length's average IOC is to the real English IOC, normalized against the worst difference among the top five so it lands in a 0-1 range, where 1 means the closest match.
    - `max_diff = e_ioc - r_ioc` which the theoretical maximum difference, between English IOC and random text IOC. 
    - `ioc_diff = abs(avg_ioc - e_ioc)`
    - `ico_score = 1 - (ioc_diff / max_diff)`

2. *Divisor quality*. In the case when the candidate key **C** is a multiple of the true key **T**, **C** and **T** would have very similar IOC closeness scores. In this case, we want to break tie. We can then score them by how good they are at evenly dividing other top candidates. If it evenly divides another candidate, its score increase `1-(klen/r)`. For example, in the case that five candidates `3, 4, 6, 12, 18`, they would have scores `(2.083, 0.667, 1.167, 0, 0)`. All `3, 4, 6` can each evenly divide some of the longer keys but we favors the shorter one that can evenly divde another short key. This is because when another candidate gets long it might just become more divisible because it is simply a big number. 

We then normalize the score by taking an average so it always falls between a 0-1 range. In this case the long key **QWEQWEQWE** would do worse than **QWE** at evenly dividing other candidates. If none of the key length can evenly divide other candidates, then all would have `divisor_score = 0` and the scoring would fall back to using entirely IOC closeness. 
    - `dividing_count = sum( 1-(klen/r) for r in rest if r % klen == 0 )`
    - `divisor_score = dividing_count / len(top candidates)`

3. Finally, we combine the two factors with a weight `alpha`, which just decide whether we favor IOC closeness or divisor quality more (with `alpha=1` being only considering IOC closeness). I tried a few values and picked `alpha=0.7`. I think IOC closeness alone is a strong signal but it does not help when candidate is a multiple of the true key. Divisor quality helps with it, but it alone would penalize a true long key too harshily. 
    - `final_score = alpha * ico_score + (1 - alpha) * divisor_score` 

Again, `alpha` is and top `n` candidates are chosen by largely eyeballing the output. I tried a few versions with `alpha=0.5` and below and they all performed horribly when the true key is genuinely long; while using only IOC closeness is not enough nuance to deal with the tie-breaking scenario. 

## Known failure cases

When the true long key has repeated patterns within (e.g., `XTSXTSXTS`), my algorithms would decide the key is `XTS`. This is because my algorithm includes an extra step that tries to detect repeated structure in the decrypted key and deduplicate. It technically is not the correct length nor content but with `XTS` the ciphertext will be decrpyted correctly regardless. So I think this is an acceptable failure.

It does not perform well when ciphertext is short while the real key is long. I think this is an universal problem for all IOC-based distribution methods. 