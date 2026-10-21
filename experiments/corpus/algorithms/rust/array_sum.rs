/// Sum all elements of a slice.
pub fn array_sum(arr: &[i32], n: usize) -> i64 {
    let mut total: i64 = 0;
    let mut i = 0;
    while i < n {
        total += arr[i] as i64;
        i += 1;
    }
    total
}
