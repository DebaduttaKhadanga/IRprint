/// In-place bubble sort.
pub fn bubble_sort(arr: &mut [i32], n: usize) {
    let mut i = 0;
    while i + 1 < n {
        let mut j = 0;
        while j + 1 < n - i {
            if arr[j] > arr[j + 1] {
                let tmp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = tmp;
            }
            j += 1;
        }
        i += 1;
    }
}
