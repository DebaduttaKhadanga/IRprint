long accumulate(int *buffer, int length)
{
    long acc = 0;
    int pos = 0;
    while (pos < length) {
        acc = acc + buffer[pos];
        pos = pos + 1;
    }
    return acc;
}
