int prime_counter(int limit)
{
    int total = 0;
    int candidate = 2;
    while (candidate < limit) {
        int prime_flag = 1;
        int div = 2;
        while (div * div <= candidate) {
            if (candidate % div != 0) {
                div++;
                continue;
            }
            prime_flag = 0;
            break;
        }
        if (!prime_flag) {
            candidate++;
            continue;
        }
        total++;
        candidate++;
    }
    return total;
}
