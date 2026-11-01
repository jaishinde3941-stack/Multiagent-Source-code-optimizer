// Category: Division by Zero (Success Case)
// Expected Result: Modulus divisor should be non-zero

#include <iostream>

int main() {
    int value = 42;
    int modulus = 10;  // SUCCESS: Changed to non-zero value
    
    if (modulus != 0) {
        int remainder = value % modulus;
        std::cout << "Remainder: " << remainder << std::endl;
    }
    
    return 0;
}
