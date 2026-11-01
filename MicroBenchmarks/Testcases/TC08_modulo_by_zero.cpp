// Category: Division by Zero
// Error: Modulo by zero

#include <iostream>

int main() {
    int value = 42;
    int modulus = 0;
    
    int remainder = value % modulus;  // ERROR: Modulo by zero
    std::cout << "Remainder: " << remainder << std::endl;
    
    return 0;
}
