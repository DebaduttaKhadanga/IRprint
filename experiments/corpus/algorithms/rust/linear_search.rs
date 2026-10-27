/// Index of the first occurrence of target, or -1.
pub fn linear_search(arr: &[i32], n: usize, target: i32) -> i32 {
    let mut i = 0;
    while i < n {
        if arr[i] == target {
            return i as i32;
        }
        i += 1;
    }
    -1
}
