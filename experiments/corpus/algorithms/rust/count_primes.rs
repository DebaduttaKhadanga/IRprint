/// Count primes below n using trial division.
pub fn count_primes(n: i32) -> i32 {
    let mut count = 0;
    let mut x = 2;
    while x < n {
        let mut is_prime = true;
        let mut d = 2;
        while d * d <= x {
            if x % d == 0 {
                is_prime = false;
                break;
            }
            d += 1;
        }
        if is_prime {
            count += 1;
        }
        x += 1;
    }
    count
}
