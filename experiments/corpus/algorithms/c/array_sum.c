/* Sum all elements of an array. */
long array_sum(int *arr, int n) {
    long total = 0;
    for (int i = 0; i < n; i++) {
        total += arr[i];
    }
    return total;
}
