// Rust port of max_a.c
pub fn max_val(arr: &[i32], n: usize) -> i32 {
    let mut m = arr[0];
    let mut i = 1;
    while i < n {
        if arr[i] > m {
            m = arr[i];
        }
        i += 1;
    }
    m
}
