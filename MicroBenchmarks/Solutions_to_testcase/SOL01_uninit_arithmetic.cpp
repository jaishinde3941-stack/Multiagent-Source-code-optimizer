// Category: Uninitialized Variables (Success Case)
// Expected Result: Variables should be initialized before use

#include <iostream>

int main() {
    int x = 0;  // SUCCESS: Initialized to 0
    int y = 10;
    
    int result = x + y;
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
