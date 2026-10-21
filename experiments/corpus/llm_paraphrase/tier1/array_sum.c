// Adds up every number in the buffer
long accumulate(int *buffer, int length)
{
    long acc = 0;
    for (int pos = 0; pos < length; pos++)
        acc += buffer[pos];
    return acc;
}
