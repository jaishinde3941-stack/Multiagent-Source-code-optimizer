// Category: Type Errors (Success Case)
// Expected Result: Avoid unsafe type punning; use safer conversion methods

#include <iostream>
#include <cstring>

int main() {
    double d = 3.14159;
    
    // SUCCESS: If intent is to see raw bytes, use memcpy or char pointers (legal)
    unsigned char bytes[sizeof(double)];
    std::memcpy(bytes, &d, sizeof(double));
    
    std::cout << "Raw bytes of double copied safely." << std::endl;
    
    return 0;
}
