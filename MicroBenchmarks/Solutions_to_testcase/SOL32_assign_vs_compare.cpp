// Category: Logic Errors (Success Case)
// Expected Result: Use comparison operator (==) instead of assignment (=)

#include <iostream>

int main() {
    int x = 5;
    
    if (x == 10) {  // SUCCESS: Used == for comparison
        std::cout << "x equals 10" << std::endl;
    } else {
        std::cout << "x does not equal 10" << std::endl;
    }
    
    std::cout << "x is still: " << x << std::endl;
    
    return 0;
}
