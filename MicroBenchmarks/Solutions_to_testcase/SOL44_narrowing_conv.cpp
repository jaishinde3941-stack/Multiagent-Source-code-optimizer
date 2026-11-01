// Category: Type Errors (Success Case)
// Expected Result: Use appropriate types or check for value range before assignment

#include <iostream>

int main() {
    long long bigValue = 123456789LL;
    
    // SUCCESS: Check range before narrowing conversion
    if (bigValue >= INT_MIN && bigValue <= INT_MAX) {
        int smallValue = (int)bigValue;
        std::cout << "Converted safely: " << smallValue << std::endl;
    } else {
        std::cout << "Value out of int range" << std::endl;
    }
    
    return 0;
}
