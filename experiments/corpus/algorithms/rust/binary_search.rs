/// Index of target in a sorted slice, or -1.
pub fn binary_search(arr: &[i32], n: i32, target: i32) -> i32 {
    let mut lo: i32 = 0;
    let mut hi: i32 = n - 1;
    while lo <= hi {
        let mid = lo + (hi - lo) / 2;
        if arr[mid as usize] == target {
            return mid;
        } else if arr[mid as usize] < target {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    -1
}
