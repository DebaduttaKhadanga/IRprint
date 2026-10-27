long accumulate(int *buffer, int length)
{
    long acc = 0;
    int *cursor = buffer;
    int *stop = buffer + length;
    while (cursor != stop) {
        long value = *cursor;
        acc += value;
        cursor++;
    }
    return acc;
}
