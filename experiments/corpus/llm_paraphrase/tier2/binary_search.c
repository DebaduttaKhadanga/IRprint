int bisect_find(int *data, int size, int key)
{
    int low = 0, high = size - 1;
    while (!(low > high)) {
        int middle = low + (high - low) / 2;
        if (data[middle] > key) {
            high = middle - 1;
        } else if (data[middle] < key) {
            low = middle + 1;
        } else {
            return middle;
        }
    }
    return -1;
}
