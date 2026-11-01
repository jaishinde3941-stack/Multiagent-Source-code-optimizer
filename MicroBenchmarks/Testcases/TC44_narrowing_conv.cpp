// Category: Type Errors
// Error: Implicit narrowing conversion

#include <iostream>

int main() {
    long long bigValue = 9223372036854775807LL;
    int smallValue = bigValue;  // ERROR: Narrowing conversion, data loss
    
    std::cout << "Original: " << bigValue << std::endl;
    std::cout << "Converted: " << smallValue << std::endl;
    
    return 0;
}
