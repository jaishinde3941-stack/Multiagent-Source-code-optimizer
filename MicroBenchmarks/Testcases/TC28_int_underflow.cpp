// Category: Integer Errors
// Error: Integer underflow

#include <iostream>
#include <climits>

int main() {
    int minInt = INT_MIN;
    int result = minInt - 1;  // ERROR: Integer underflow (undefined behavior)
    
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
