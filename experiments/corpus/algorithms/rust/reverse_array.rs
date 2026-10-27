/// Reverse a slice in place.
pub fn reverse_array(arr: &mut [i32], n: usize) {
    if n == 0 {
        return;
    }
    let mut left = 0;
    let mut right = n - 1;
    while left < right {
        let tmp = arr[left];
        arr[left] = arr[right];
        arr[right] = tmp;
        left += 1;
        right -= 1;
    }
}
