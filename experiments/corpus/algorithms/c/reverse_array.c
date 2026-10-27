/* Reverse an array in place. */
void reverse_array(int *arr, int n) {
    int left = 0;
    int right = n - 1;
    while (left < right) {
        int tmp = arr[left];
        arr[left] = arr[right];
        arr[right] = tmp;
        left++;
        right--;
    }
}
