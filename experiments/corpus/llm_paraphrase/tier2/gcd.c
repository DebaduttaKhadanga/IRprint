int highest_common_factor(int first, int second)
{
    for (;;) {
        if (second == 0)
            break;
        int remainder = first % second;
        first = second;
        second = remainder;
    }
    return first;
}
