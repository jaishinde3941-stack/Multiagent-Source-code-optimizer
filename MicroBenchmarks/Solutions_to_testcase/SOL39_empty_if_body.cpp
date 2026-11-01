// Category: Control Flow Errors (Success Case)
// Expected Result: Avoid accidental semicolons after if-conditions

#include <iostream>

int main() {
    int x = 5;
    
    if (x > 0) {  // SUCCESS: Removed extra semicolon
        std::cout << "x is positive" << std::endl;
    }
    
    return 0;
}
