int bisect_find(int *data, int size, int key)
{
    int low = 0, span = size;
    while (span > 0) {
        int half = span >> 1;
        int probe = low + half;
        int v = data[probe];
        if (v == key)
            return probe;
        int go_right = v < key;
        low = go_right ? probe + 1 : low;
        span = go_right ? span - half - 1 : half;
    }
    return -1;
}
