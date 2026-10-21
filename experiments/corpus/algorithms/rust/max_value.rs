/// Return the largest element of a slice.
pub fn max_value(arr: &[i32], n: usize) -> i32 {
    let mut best = arr[0];
    let mut i = 1;
    while i < n {
        if arr[i] > best {
            best = arr[i];
        }
        i += 1;
    }
    best
}
