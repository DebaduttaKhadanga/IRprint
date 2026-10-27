/* Return the largest element of an array. */
int max_value(int *arr, int n) {
    int best = arr[0];
    for (int i = 1; i < n; i++) {
        if (arr[i] > best) {
            best = arr[i];
        }
    }
    return best;
}
