/// n-th Fibonacci number, iterative.
pub fn fibonacci(n: i32) -> i64 {
    let mut a: i64 = 0;
    let mut b: i64 = 1;
    let mut i = 0;
    while i < n {
        let next = a + b;
        a = b;
        b = next;
        i += 1;
    }
    a
}
