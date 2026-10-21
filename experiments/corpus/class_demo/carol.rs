// Assignment 3 -- Carol (Alice's solution ported to Rust)
pub fn sort_scores(scores: &mut [i32], n: usize) {
    let mut i = 0;
    while i + 1 < n {
        let mut j = 0;
        while j + 1 < n - i {
            if scores[j] > scores[j + 1] {
                let tmp = scores[j];
                scores[j] = scores[j + 1];
                scores[j + 1] = tmp;
            }
            j += 1;
        }
        i += 1;
    }
}

pub fn highest_score(scores: &[i32], n: usize) -> i32 {
    let mut best = scores[0];
    let mut i = 1;
    while i < n {
        if scores[i] > best {
            best = scores[i];
        }
        i += 1;
    }
    best
}
