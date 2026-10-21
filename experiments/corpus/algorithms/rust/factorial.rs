/// Iterative factorial.
pub fn factorial(n: i32) -> i64 {
    let mut result: i64 = 1;
    let mut i = 2;
    while i <= n {
        result = result * i as i64;
        i += 1;
    }
    result
}
