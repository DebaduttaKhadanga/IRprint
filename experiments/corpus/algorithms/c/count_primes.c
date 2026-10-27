/* Count primes below n using trial division. */
int count_primes(int n) {
    int count = 0;
    for (int x = 2; x < n; x++) {
        int is_prime = 1;
        for (int d = 2; d * d <= x; d++) {
            if (x % d == 0) {
                is_prime = 0;
                break;
            }
        }
        if (is_prime) {
            count++;
        }
    }
    return count;
}
