// Assignment 3 -- Grace (independent Rust solution: histogram + mode)
pub fn histogram(scores: &[i32], buckets: &mut [i32]) {
    for s in scores.iter() {
        let mut idx = (*s / 10) as usize;
        if idx >= buckets.len() {
            idx = buckets.len() - 1;
        }
        buckets[idx] += 1;
    }
}

pub fn mode_bucket(buckets: &[i32]) -> usize {
    let mut best = 0;
    let mut i = 1;
    while i < buckets.len() {
        if buckets[i] > buckets[best] {
            best = i;
        }
        i += 1;
    }
    best
}
